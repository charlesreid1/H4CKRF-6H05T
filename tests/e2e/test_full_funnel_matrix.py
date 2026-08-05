"""Table-driven e2e test: one row per (CommandAction, tier) combination.

Catches regressions where a new action's risk classification silently drifts.
"""

from __future__ import annotations

import asyncio

import pytest

from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.approval import AlwaysAllowApprovalPort
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.executor import CommandExecutor
from hackrf_agent.domain.models import (
    AuditEventType,
    CommandAction,
    ExecuteCommand,
    RiskLevel,
)
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.result_formatter import ResultFormatter
from hackrf_agent.domain.risk_assessor import RiskAssessor
from hackrf_agent.domain.session import new_session
from tests.support.fake_driver import FakeDriver

# One row per (action, args) combination that exercises a distinct
# risk classification. NOT exhaustive — one row per tier per action
# is enough for regression detection.
MATRIX = [
    # (action, args, expected_tier, expected_event_count, driver_called)
    (CommandAction.GET_DEVICE_INFO, {}, RiskLevel.LOW, 4, True),
    (
        CommandAction.SWEEP_SPECTRUM,
        {
            "start_freq_hz": 433_000_000,
            "end_freq_hz": 434_000_000,
            "sample_rate_hz": 2_000_000,
            "dwell_s": 0.1,
        },
        RiskLevel.LOW,
        4,
        True,
    ),
    (
        CommandAction.CAPTURE_IQ,
        {"center_freq_hz": 433_925_000, "sample_rate_hz": 2_000_000, "duration_s": 1.0},
        RiskLevel.LOW,
        4,
        True,
    ),
    (
        CommandAction.CAPTURE_IQ,
        {"center_freq_hz": 433_925_000, "sample_rate_hz": 2_000_000, "duration_s": 10.0},
        RiskLevel.MEDIUM,
        6,
        True,
    ),
    (
        CommandAction.TRANSMIT_IQ,
        {
            "center_freq_hz": 1_090_000_000,
            "sample_rate_hz": 2_000_000,
            "tx_vga_gain_db": 10,
            "iq_path": "/nonexistent.iq",
        },
        RiskLevel.BLOCKED,
        3,
        False,
    ),
    (
        CommandAction.TRANSMIT_IQ,
        {
            "center_freq_hz": 900_000_000,
            "sample_rate_hz": 2_000_000,
            "tx_vga_gain_db": 10,
            "iq_path": "/nonexistent.iq",
        },
        RiskLevel.HIGH,
        6,
        False,
    ),
    (
        CommandAction.ANALYZE_PULSES,
        {"iq_path": "/nonexistent.iq", "sample_rate_hz": 2_000_000},
        RiskLevel.LOW,
        4,
        False,
    ),
    (
        CommandAction.DEMODULATE_BITS,
        {
            "iq_path": "/nonexistent.iq",
            "sample_rate_hz": 2_000_000,
            "modulation": "ASK",
            "samples_per_symbol": 100,
        },
        RiskLevel.LOW,
        4,
        False,
    ),
]


def _param_id(val):
    """Generate human-readable parametrize ids."""
    if isinstance(val, CommandAction):
        return val.value
    if isinstance(val, RiskLevel):
        return val.value
    return str(val)


@pytest.mark.parametrize(
    "action,args,tier,n_events,driver_called",
    MATRIX,
    ids=lambda p: _param_id(p) if not isinstance(p, dict) else "",
)
async def test_funnel_row(tmp_path, action, args, tier, n_events, driver_called):
    db = tmp_path / "agent.db"
    await ensure_schema(db)
    driver = FakeDriver()
    async with AuditService(db) as audit:
        executor = CommandExecutor(
            session_id="matrix",
            risk_assessor=RiskAssessor(),
            permissions=PermissionService(db),
            audit=audit,
            driver=driver,
            formatter=ResultFormatter(),
            approval=AlwaysAllowApprovalPort(),
            session_paths=new_session(tmp_path / "sessions"),
        )
        cmd = ExecuteCommand(
            action=action,
            args=args,
            justification="matrix",
            expected_effect="matrix",
        )
        await executor.execute(cmd)
        # Give the audit writer a chance to drain.
        await asyncio.sleep(0.05)
        rows = await audit.query(session_id="matrix", limit=100)

    # Same trace_id across all rows.
    assert len({r.trace_id for r in rows}) == 1
    assert len(rows) == n_events
    # Risk tier stamped on the RISK_ASSESSED row.
    risk_row = [r for r in rows if r.event == AuditEventType.RISK_ASSESSED][0]
    assert risk_row.risk_level == tier
    # Driver call count matches expectation.
    if driver_called:
        assert len(driver.calls) >= 1
    else:
        assert driver.calls == []
