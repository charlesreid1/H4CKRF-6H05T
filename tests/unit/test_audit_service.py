"""Unit tests for ``AuditService`` — queued writer, query, and helpers."""

import asyncio
import json
from uuid import uuid4

import pytest

from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.audit_service import (
    AuditService,
    make_event,
    new_trace_id,
)
from hackrf_agent.domain.models import AuditEventType, CommandAction, RiskLevel

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def audit(tmp_path):
    """An AuditService pointed at a temp file, with schema applied, started."""
    db = tmp_path / "agent.db"
    await ensure_schema(db)
    async with AuditService(db) as svc:
        yield svc


# ---------------------------------------------------------------------------
# Basic insert / query
# ---------------------------------------------------------------------------


class TestBasicWriteRead:
    async def test_log_one_event_returns_in_query(self, audit):
        trace = uuid4()
        await audit.log(
            make_event(
                trace_id=trace,
                session_id="s1",
                event=AuditEventType.COMMAND_RECEIVED,
                action=CommandAction.GET_DEVICE_INFO,
            )
        )
        # Must drain before querying — stop() drains.
        await audit.stop()
        # Re-open for reading.
        async with AuditService(audit._db_path) as svc:
            rows = await svc.query(trace_id=trace)
        assert len(rows) == 1
        assert rows[0].id == 1
        assert rows[0].event == AuditEventType.COMMAND_RECEIVED

    async def test_log_five_events_ids_sequential(self, audit):
        traces = [uuid4() for _ in range(5)]
        for trace in traces:
            await audit.log(
                make_event(
                    trace_id=trace,
                    session_id="s1",
                    event=AuditEventType.COMMAND_RECEIVED,
                    action=CommandAction.GET_DEVICE_INFO,
                )
            )
        await audit.stop()
        async with AuditService(audit._db_path) as svc:
            rows = await svc.query(limit=10)
        assert [r.id for r in rows] == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Concurrent writes
# ---------------------------------------------------------------------------


class TestConcurrentWrites:
    async def test_concurrent_writes_all_land_monotonic(self, audit):
        """100 events across 10 producers — all land with strictly monotonic ids."""
        num_producers = 10
        events_per = 10

        async def producer(pid: int):
            for _ in range(events_per):
                await audit.log(
                    make_event(
                        trace_id=uuid4(),
                        session_id=f"s-{pid}",
                        event=AuditEventType.COMMAND_RECEIVED,
                        action=CommandAction.GET_DEVICE_INFO,
                    )
                )

        tasks = [asyncio.create_task(producer(p)) for p in range(num_producers)]
        await asyncio.gather(*tasks)
        await audit.stop()

        async with AuditService(audit._db_path) as svc:
            rows = await svc.query(limit=200)
        assert len(rows) == num_producers * events_per
        ids = [r.id for r in rows]
        assert ids == list(range(1, len(ids) + 1))


# ---------------------------------------------------------------------------
# Query filters
# ---------------------------------------------------------------------------


class TestQueryFilters:
    @pytest.fixture
    async def populated(self, tmp_path):
        """An AuditService with five diverse events already written and drained."""
        db = tmp_path / "agent.db"
        await ensure_schema(db)
        trace_a = uuid4()
        trace_b = uuid4()
        async with AuditService(db) as svc:
            await svc.log(
                make_event(
                    trace_id=trace_a,
                    session_id="s1",
                    event=AuditEventType.COMMAND_RECEIVED,
                    action=CommandAction.SWEEP_SPECTRUM,
                    risk_level=None,
                )
            )
            await svc.log(
                make_event(
                    trace_id=trace_a,
                    session_id="s1",
                    event=AuditEventType.RISK_ASSESSED,
                    action=CommandAction.SWEEP_SPECTRUM,
                    risk_level=RiskLevel.LOW,
                )
            )
            await svc.log(
                make_event(
                    trace_id=trace_b,
                    session_id="s2",
                    event=AuditEventType.COMMAND_RECEIVED,
                    action=CommandAction.TRANSMIT_IQ,
                    risk_level=None,
                )
            )
            await svc.log(
                make_event(
                    trace_id=trace_b,
                    session_id="s2",
                    event=AuditEventType.BLOCKED,
                    action=CommandAction.TRANSMIT_IQ,
                    risk_level=RiskLevel.BLOCKED,
                    blocked_reason="ADS-B restricted",
                )
            )
            await svc.log(
                make_event(
                    trace_id=trace_b,
                    session_id="s2",
                    event=AuditEventType.RESULT,
                    action=CommandAction.TRANSMIT_IQ,
                    risk_level=RiskLevel.BLOCKED,
                )
            )
        return db, trace_a, trace_b

    async def test_filter_by_session(self, populated):
        db, trace_a, trace_b = populated
        async with AuditService(db) as svc:
            rows = await svc.query(session_id="s1")
        assert len(rows) == 2
        assert all(r.session_id == "s1" for r in rows)

    async def test_filter_by_trace_id(self, populated):
        db, trace_a, trace_b = populated
        async with AuditService(db) as svc:
            rows = await svc.query(trace_id=trace_a)
        assert len(rows) == 2
        assert all(r.trace_id == trace_a for r in rows)

    async def test_filter_by_risk_level(self, populated):
        db, trace_a, trace_b = populated
        async with AuditService(db) as svc:
            rows = await svc.query(risk_level=RiskLevel.BLOCKED)
        assert len(rows) == 2
        assert all(r.risk_level == RiskLevel.BLOCKED for r in rows)

    async def test_filter_by_event_type(self, populated):
        db, trace_a, trace_b = populated
        async with AuditService(db) as svc:
            rows = await svc.query(event=AuditEventType.COMMAND_RECEIVED)
        assert len(rows) == 2
        assert all(r.event == AuditEventType.COMMAND_RECEIVED for r in rows)

    async def test_limit_respected(self, populated):
        db, trace_a, trace_b = populated
        async with AuditService(db) as svc:
            rows = await svc.query(limit=3)
        assert len(rows) == 3


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    async def test_log_before_start_raises(self, tmp_path):
        db = tmp_path / "agent.db"
        await ensure_schema(db)
        svc = AuditService(db)
        trace = uuid4()
        with pytest.raises(RuntimeError, match="before start"):
            await svc.log(
                make_event(
                    trace_id=trace,
                    session_id="s1",
                    event=AuditEventType.COMMAND_RECEIVED,
                )
            )

    async def test_async_context_drains_on_exit(self, tmp_path):
        """Events enqueued just before context exit land in the DB."""
        db = tmp_path / "agent.db"
        await ensure_schema(db)
        trace = uuid4()
        async with AuditService(db) as svc:
            await svc.log(
                make_event(
                    trace_id=trace,
                    session_id="s1",
                    event=AuditEventType.COMMAND_RECEIVED,
                )
            )
            await svc.log(
                make_event(
                    trace_id=trace,
                    session_id="s1",
                    event=AuditEventType.RISK_ASSESSED,
                    risk_level=RiskLevel.LOW,
                )
            )
            await svc.log(
                make_event(
                    trace_id=trace,
                    session_id="s1",
                    event=AuditEventType.EXECUTED,
                )
            )
            await svc.log(
                make_event(
                    trace_id=trace,
                    session_id="s1",
                    event=AuditEventType.RESULT,
                )
            )
            await svc.log(
                make_event(
                    trace_id=trace,
                    session_id="s1",
                    event=AuditEventType.RESULT,  # intentional duplicate — allowed
                )
            )

        # After context exit, all 5 should be persisted.
        async with AuditService(db) as svc:
            rows = await svc.query(trace_id=trace)
        assert len(rows) == 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    async def test_make_event_payload_roundtrip(self, audit):
        trace = uuid4()
        await audit.log(
            make_event(
                trace_id=trace,
                session_id="s1",
                event=AuditEventType.COMMAND_RECEIVED,
                action=CommandAction.CAPTURE_IQ,
                payload={"freq_hz": 433_920_000, "samples": 1_000_000},
            )
        )
        await audit.stop()
        async with AuditService(audit._db_path) as svc:
            rows = await svc.query(trace_id=trace)
        assert len(rows) == 1
        assert rows[0].payload_json is not None
        data = json.loads(rows[0].payload_json)  # type: ignore[arg-type]
        assert data == {"freq_hz": 433_920_000, "samples": 1_000_000}

    def test_new_trace_id_is_uuid(self):
        tid = new_trace_id()
        assert isinstance(tid, uuid4().__class__)

    def test_new_trace_ids_are_distinct(self):
        ids = {new_trace_id() for _ in range(50)}
        assert len(ids) == 50


# ---------------------------------------------------------------------------
# Query ordering — limit returns most recent, not oldest
# ---------------------------------------------------------------------------


class TestQueryOrdering:
    async def test_query_returns_last_n_not_first_n(self, tmp_path):
        """limit=3 with 10 events should return events 8,9,10 (most recent)."""
        from hackrf_agent.domain.audit_service import AuditService, make_event
        from hackrf_agent.data.db import ensure_schema

        db = tmp_path / "agent.db"
        await ensure_schema(db)

        async with AuditService(db) as svc:
            for i in range(10):
                await svc.log(
                    make_event(
                        trace_id=uuid4(),
                        session_id="s1",
                        event=AuditEventType.COMMAND_RECEIVED,
                        action=CommandAction.GET_DEVICE_INFO,
                    )
                )
        # Context exit drains — all 10 events persisted.

        async with AuditService(db) as svc:
            rows = await svc.query(limit=3)

        assert len(rows) == 3
        # IDs are 1-indexed; the 3 most recent of 10 are 8, 9, 10.
        assert [r.id for r in rows] == [8, 9, 10]
        # Chronological: oldest→newest within the window.
        assert rows[0].id < rows[-1].id
