"""Integration smoke test — AuditService and PermissionService coexist on one DB."""

from uuid import uuid4

from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.audit_service import AuditService, make_event
from hackrf_agent.domain.models import AuditEventType, CommandAction, RiskLevel
from hackrf_agent.domain.permission_service import PermissionService


async def test_audit_and_permissions_share_db(tmp_path):
    """Both services on the same file — no WAL contention, no data loss."""
    db = tmp_path / "agent.db"
    await ensure_schema(db)

    perms = PermissionService(db)

    async with AuditService(db) as audit:
        # Create a TX grant.
        grant = await perms.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )

        # Log a few lifecycle events.
        trace = uuid4()
        await audit.log(make_event(
            trace_id=trace, session_id="s1",
            event=AuditEventType.COMMAND_RECEIVED,
            action=CommandAction.TRANSMIT_IQ,
            payload={"grant_id": str(grant.id)},
        ))
        await audit.log(make_event(
            trace_id=trace, session_id="s1",
            event=AuditEventType.RISK_ASSESSED,
            action=CommandAction.TRANSMIT_IQ,
            risk_level=RiskLevel.MEDIUM,
        ))
        # Context exit drains the writer.

    # Smoke-check: re-open and verify.
    async with AuditService(db) as svc:
        rows = await svc.query(trace_id=trace)
    assert [r.event for r in rows] == [
        AuditEventType.COMMAND_RECEIVED,
        AuditEventType.RISK_ASSESSED,
    ]

    # Grant should still be active (not revoked, not expired).
    active = await perms.list_active()
    assert active == [grant]
