"""Append-only audit writer with a single background coroutine.

Writes funnel through an ``asyncio.Queue`` consumed by one long-lived
writer task.  Readers open their own short-lived connections so they
never block behind the writer.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

import aiosqlite

from hackrf_agent.data.db import open_connection
from hackrf_agent.domain.models import (
    AuditEvent,
    AuditEventType,
    CommandAction,
    RiskLevel,
)

# ---------------------------------------------------------------------------
# Sentinel — stops the writer loop cleanly
# ---------------------------------------------------------------------------

_SHUTDOWN_SENTINEL: Final[object] = object()

# ---------------------------------------------------------------------------
# Read-side row
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditRow:
    """Read-side row shape.  Mirrors *AuditEvent* + the DB-assigned ``id``."""

    id: int
    trace_id: UUID
    session_id: str
    timestamp: float
    event: AuditEventType
    action: CommandAction | None
    risk_level: RiskLevel | None
    payload_json: str | None
    blocked_reason: str | None
    duration_ms: int | None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AuditService:
    """Append-only audit log backed by SQLite.

    One background writer coroutine owns the write connection; ``log()``
    enqueues events and returns immediately.  ``query()`` reads from a
    fresh connection so reads never contend with the writer.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = db_path
        self._queue: asyncio.Queue[AuditEvent | object] = asyncio.Queue()
        self._writer_task: asyncio.Task[None] | None = None
        self._started = False

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Spawn the background writer coroutine.  Idempotent."""
        if self._started:
            return
        self._writer_task = asyncio.create_task(
            self._writer_loop(), name="audit-writer"
        )
        self._started = True

    async def stop(self) -> None:
        """Drain the queue and cancel the writer."""
        if not self._started:
            return
        await self._queue.put(_SHUTDOWN_SENTINEL)
        assert self._writer_task is not None
        await self._writer_task
        self._writer_task = None
        self._started = False

    async def __aenter__(self) -> AuditService:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()

    # -- write ----------------------------------------------------------------

    async def log(self, event: AuditEvent) -> None:
        """Enqueue an event for the writer.  Non-blocking from the caller's POV.

        .. note::
           ``event.payload_json`` is stored verbatim.  Never dump raw LLM
           messages or credentials into it — audit rows are read by humans
           and by future replay tooling.
        """
        if not self._started:
            raise RuntimeError("AuditService.log() called before start()")
        await self._queue.put(event)

    # -- read ----------------------------------------------------------------

    async def query(
        self,
        *,
        session_id: str | None = None,
        trace_id: UUID | None = None,
        risk_level: RiskLevel | None = None,
        event: AuditEventType | None = None,
        limit: int = 100,
    ) -> list[AuditRow]:
        """Read from a fresh connection.  Filters combine with AND.

        Rows are ordered by ``id ASC`` (write order).  At most *limit*
        rows are returned.
        """
        clauses: list[str] = []
        params: list[object] = []

        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if trace_id is not None:
            clauses.append("trace_id = ?")
            params.append(str(trace_id))
        if risk_level is not None:
            clauses.append("risk_level = ?")
            params.append(risk_level.value)
        if event is not None:
            clauses.append("event = ?")
            params.append(event.value)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))

        sql = (
            "SELECT id, trace_id, session_id, timestamp, event, action, "
            "risk_level, payload_json, blocked_reason, duration_ms "
            f"FROM audit {where} ORDER BY id ASC LIMIT ?;"
        )

        async with open_connection(self._db_path) as conn:  # noqa: SIM117
            async with conn.execute(sql, params) as cur:
                rows = await cur.fetchall()

        return [self._row_to_audit(r) for r in rows]

    # -- internals -----------------------------------------------------------

    async def _writer_loop(self) -> None:
        """Consume from the queue and INSERT until the sentinel arrives."""
        async with open_connection(self._db_path) as conn:
            while True:
                item = await self._queue.get()
                if item is _SHUTDOWN_SENTINEL:
                    await conn.commit()
                    return
                assert isinstance(item, AuditEvent)
                await self._insert(conn, item)
                # Commit per event.  Correctness > throughput at this scale.
                # If audit throughput ever becomes a bottleneck, batch here
                # with a time+count threshold — but don't optimise preemptively.
                await conn.commit()

    async def _insert(self, conn: aiosqlite.Connection, ev: AuditEvent) -> None:
        await conn.execute(
            "INSERT INTO audit ("
            " trace_id, session_id, timestamp, event, action, risk_level, "
            " payload_json, blocked_reason, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                str(ev.trace_id),
                ev.session_id,
                ev.timestamp,
                ev.event.value,
                ev.action.value if ev.action else None,
                ev.risk_level.value if ev.risk_level else None,
                ev.payload_json,
                ev.blocked_reason,
                ev.duration_ms,
            ),
        )

    @staticmethod
    def _row_to_audit(row: object) -> AuditRow:
        row = tuple(row)  # type: ignore[arg-type]
        return AuditRow(
            id=row[0],
            trace_id=UUID(row[1]),
            session_id=row[2],
            timestamp=row[3],
            event=AuditEventType(row[4]),
            action=CommandAction(row[5]) if row[5] else None,
            risk_level=RiskLevel(row[6]) if row[6] else None,
            payload_json=row[7],
            blocked_reason=row[8],
            duration_ms=row[9],
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def make_event(
    *,
    trace_id: UUID,
    session_id: str,
    event: AuditEventType,
    action: CommandAction | None = None,
    risk_level: RiskLevel | None = None,
    payload: dict[str, object] | None = None,
    blocked_reason: str | None = None,
    duration_ms: int | None = None,
) -> AuditEvent:
    """Convenience constructor that stamps ``timestamp = time.time()`` and
    serialises *payload* to JSON.

    If *payload* contains non-JSON-serialisable values, this raises
    ``TypeError`` at construction — good; catch the bug in dev, not
    in prod.
    """
    return AuditEvent(
        trace_id=trace_id,
        session_id=session_id,
        timestamp=time.time(),
        event=event,
        action=action,
        risk_level=risk_level,
        payload_json=json.dumps(payload, separators=(",", ":")) if payload else None,
        blocked_reason=blocked_reason,
        duration_ms=duration_ms,
    )


def new_trace_id() -> UUID:
    """Executor mints one of these per *ExecuteCommand*.

    Kept here so callers don't reach for ``uuid4`` directly and forget.
    """
    return uuid4()
