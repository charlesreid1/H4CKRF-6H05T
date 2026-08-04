"""CRUD around *Grant* objects backed by SQLite.

Writes are rare (a human types ``hackrf-agent grant tx …`` at the CLI,
or the kill switch revokes en masse), so no writer coroutine is needed
— direct ``INSERT`` / ``UPDATE`` per call.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from hackrf_agent.data.db import open_connection
from hackrf_agent.domain.models import Grant, _utcnow


class PermissionService:
    """Grant persistence with TTL-aware read.

    TTL is enforced at *read time* via ``list_active()`` — no background
    sweep.  Expired grants simply stop appearing in the active list.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = db_path

    # -- create ---------------------------------------------------------------

    async def grant(
        self,
        *,
        kind: str = "tx",
        band_start_hz: int,
        band_stop_hz: int,
        max_gain_db: int,
        ttl_seconds: int,
    ) -> Grant:
        """Create and persist a new grant.  Returns the persisted *Grant*."""
        if band_start_hz >= band_stop_hz:
            raise ValueError("band_start_hz must be < band_stop_hz")
        if max_gain_db < 0:
            raise ValueError("max_gain_db must be >= 0")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")

        now = _utcnow()
        grant = Grant(
            kind=kind,
            band_start_hz=band_start_hz,
            band_stop_hz=band_stop_hz,
            max_gain_db=max_gain_db,
            granted_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

        async with open_connection(self._db_path) as conn:
            await conn.execute(
                "INSERT INTO grants (id, kind, band_start_hz, band_stop_hz, "
                " max_gain_db, granted_at, expires_at, revoked_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, NULL);",
                (
                    str(grant.id),
                    grant.kind,
                    grant.band_start_hz,
                    grant.band_stop_hz,
                    grant.max_gain_db,
                    grant.granted_at.timestamp(),
                    grant.expires_at.timestamp(),
                ),
            )
            await conn.commit()

        return grant

    # -- read -----------------------------------------------------------------

    async def list_active(self, *, kind: str | None = None) -> list[Grant]:
        """Return all grants that are neither expired nor revoked.

        If *kind* is given, filter to that grant kind.  Ordered by
        ``expires_at ASC`` so the soonest-to-expire sorts first.
        """
        now_epoch = _utcnow().timestamp()
        clauses = ["revoked_at IS NULL", "expires_at > ?"]
        params: list[object] = [now_epoch]

        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)

        sql = (
            "SELECT id, kind, band_start_hz, band_stop_hz, max_gain_db, "
            " granted_at, expires_at, revoked_at "
            f"FROM grants WHERE {' AND '.join(clauses)} "
            "ORDER BY expires_at ASC;"
        )

        async with open_connection(self._db_path) as conn:  # noqa: SIM117
            async with conn.execute(sql, params) as cur:
                rows = await cur.fetchall()

        return [self._row_to_grant(r) for r in rows]

    async def list_all(self) -> list[Grant]:
        """Every grant ever, including expired and revoked.

        Ordered newest-first by ``granted_at``.
        """
        async with open_connection(self._db_path) as conn:  # noqa: SIM117
            async with conn.execute(
                "SELECT id, kind, band_start_hz, band_stop_hz, max_gain_db, "
                " granted_at, expires_at, revoked_at "
                "FROM grants ORDER BY granted_at DESC;"
            ) as cur:
                rows = await cur.fetchall()

        return [self._row_to_grant(r) for r in rows]

    async def get(self, grant_id: UUID) -> Grant | None:
        """Return a single grant by id, or ``None``."""
        async with open_connection(self._db_path) as conn:  # noqa: SIM117
            async with conn.execute(
                "SELECT id, kind, band_start_hz, band_stop_hz, max_gain_db, "
                " granted_at, expires_at, revoked_at "
                "FROM grants WHERE id = ?;",
                (str(grant_id),),
            ) as cur:
                row = await cur.fetchone()

        return self._row_to_grant(row) if row else None

    # -- update ---------------------------------------------------------------

    async def revoke(self, grant_id: UUID) -> bool:
        """Mark a grant revoked.  Returns ``True`` iff a row was updated.

        Calling ``revoke`` on an already-revoked grant returns ``False``
        — callers can distinguish "I just revoked it" from "it was already
        revoked."
        """
        now_epoch = _utcnow().timestamp()
        async with open_connection(self._db_path) as conn:
            cur = await conn.execute(
                "UPDATE grants SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL;",
                (now_epoch, str(grant_id)),
            )
            await conn.commit()
            return cur.rowcount > 0

    async def revoke_all_tx(self) -> int:
        """Kill-switch hook (Part 7).  Revoke every currently-active TX grant.

        Returns the number of grants revoked.  Idempotent — a second call
        after the first returns 0 because there are no more active grants.
        """
        now_epoch = _utcnow().timestamp()
        async with open_connection(self._db_path) as conn:
            cur = await conn.execute(
                "UPDATE grants SET revoked_at = ? "
                "WHERE kind = 'tx' AND revoked_at IS NULL "
                "  AND expires_at > ?;",
                (now_epoch, now_epoch),
            )
            await conn.commit()
            return cur.rowcount

    # -- internals ------------------------------------------------------------

    @staticmethod
    def _row_to_grant(row: object) -> Grant:
        row = tuple(row)  # type: ignore[arg-type]
        return Grant(
            id=UUID(row[0]),
            kind=row[1],
            band_start_hz=row[2],
            band_stop_hz=row[3],
            max_gain_db=row[4],
            granted_at=datetime.fromtimestamp(row[5], tz=UTC),
            expires_at=datetime.fromtimestamp(row[6], tz=UTC),
            revoked_at=datetime.fromtimestamp(row[7], tz=UTC) if row[7] else None,
        )
