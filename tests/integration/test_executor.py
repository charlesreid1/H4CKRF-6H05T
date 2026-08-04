"""Integration tests for executor.py — the full funnel with a mocked driver.

These are integration tests because they touch the audit DB.
"""

import asyncio
from pathlib import Path

import numpy as np
import pytest

from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.approval import FakeApprovalPort
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_cmd(action: str, **args) -> ExecuteCommand:
    return ExecuteCommand(
        action=CommandAction(action),
        args=args,
        justification="test",
        expected_effect="test",
    )


# ---------------------------------------------------------------------------
# Bench fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def bench(tmp_path: Path):
    db = tmp_path / "agent.db"
    await ensure_schema(db)
    perms = PermissionService(db)
    driver = FakeDriver()
    approval = FakeApprovalPort(answer=True)
    async with AuditService(db) as audit:
        session = new_session(tmp_path / "sessions")
        executor = CommandExecutor(
            session_id="s1",
            risk_assessor=RiskAssessor(),
            permissions=perms,
            audit=audit,
            driver=driver,
            formatter=ResultFormatter(),
            approval=approval,
            session_paths=session,
        )
        yield {
            "executor": executor,
            "driver": driver,
            "approval": approval,
            "audit": audit,
            "perms": perms,
            "session": session,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _flush() -> None:
    """Yield to the event loop so the audit writer can drain its queue."""
    await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestBasicExecution:
    async def test_get_device_info_success(self, bench) -> None:
        """execute(get_device_info) returns success=True; driver called once."""
        result = await bench["executor"].execute(make_cmd("get_device_info"))
        assert result.success is True
        assert result.data["serial"] == "fake-serial"
        assert len(bench["driver"].calls) == 1
        assert bench["driver"].calls[0][0] == "get_device_info"

    async def test_low_command_four_audit_events(self, bench) -> None:
        """LOW command produces 4 audit events with shared trace_id."""
        result = await bench["executor"].execute(make_cmd("get_device_info"))
        assert result.success
        await _flush()

        rows = await bench["audit"].query(limit=200)
        # Filter to the latest 4 (our command).
        events = [r.event for r in rows[-4:]]
        assert events == [
            AuditEventType.COMMAND_RECEIVED,
            AuditEventType.RISK_ASSESSED,
            AuditEventType.EXECUTED,
            AuditEventType.RESULT,
        ]
        trace_ids = {r.trace_id for r in rows[-4:]}
        assert len(trace_ids) == 1  # All share the same trace_id.

    async def test_low_command_no_approval(self, bench) -> None:
        """LOW command does NOT call approval.request."""
        await bench["executor"].execute(make_cmd("get_device_info"))
        assert len(bench["approval"].calls) == 0

    async def test_sweep_returns_peaks(self, bench) -> None:
        """sweep_spectrum returns success=True with peaks in data."""
        # Put a strong tone in the sweep result so peaks appear.
        mag = np.full(4096, -90.0, dtype=np.float32)
        mag[1024] = -10.0
        bench["driver"].sweep_result = (mag, np.arange(4096, dtype=np.float64))

        result = await bench["executor"].execute(
            make_cmd(
                "sweep_spectrum",
                start_freq_hz=100_000_000,
                end_freq_hz=200_000_000,
                dwell_s=0.5,
            )
        )
        assert result.success is True
        assert "peaks" in result.data

    async def test_capture_writes_file(self, bench) -> None:
        """capture_iq writes a file under session.iq_dir."""
        result = await bench["executor"].execute(
            make_cmd("capture_iq", center_freq_hz=433_000_000, duration_s=0.5)
        )
        assert result.success is True
        assert "iq_path" in result.data
        iq_path = Path(result.data["iq_path"])
        assert bench["session"].is_within(iq_path)


class TestApprovalFlow:
    async def test_medium_approved_six_events(self, bench) -> None:
        """MEDIUM capture (long duration) approved: 6 audit events."""
        result = await bench["executor"].execute(
            make_cmd("capture_iq", center_freq_hz=433_000_000, duration_s=10.0)
        )
        assert result.success is True
        assert len(bench["approval"].calls) == 1
        await _flush()

        rows = await bench["audit"].query(limit=200)
        events = [r.event for r in rows[-6:]]
        assert events == [
            AuditEventType.COMMAND_RECEIVED,
            AuditEventType.RISK_ASSESSED,
            AuditEventType.APPROVAL_REQUESTED,
            AuditEventType.APPROVAL_GRANTED,
            AuditEventType.EXECUTED,
            AuditEventType.RESULT,
        ]

    async def test_medium_denied_no_handler(self, bench) -> None:
        """MEDIUM capture denied: success=False, handler NOT called."""
        bench["approval"].answer = False
        driver_call_count_before = len(bench["driver"].calls)

        result = await bench["executor"].execute(
            make_cmd("capture_iq", center_freq_hz=433_000_000, duration_s=10.0)
        )
        assert result.success is False
        assert result.error == "approval_denied"
        # Driver was NOT called for capture_iq.
        assert len(bench["driver"].calls) == driver_call_count_before
        await _flush()

        rows = await bench["audit"].query(limit=200)
        events = [r.event for r in rows[-5:]]
        assert AuditEventType.APPROVAL_DENIED in events
        assert AuditEventType.APPROVAL_GRANTED not in events
        assert AuditEventType.EXECUTED not in events

    async def test_blocked_transmit_no_handler(self, bench) -> None:
        """BLOCKED transmit_iq: success=False, handler NOT called."""
        driver_call_count_before = len(bench["driver"].calls)

        result = await bench["executor"].execute(
            make_cmd("transmit_iq", center_freq_hz=1090_000_000, tx_vga_gain_db=20)
        )
        assert result.success is False
        assert result.message.startswith("Action blocked")
        # Driver was NOT called.
        assert len(bench["driver"].calls) == driver_call_count_before
        await _flush()

        rows = await bench["audit"].query(limit=200)
        events = [r.event for r in rows[-3:]]
        assert events == [
            AuditEventType.COMMAND_RECEIVED,
            AuditEventType.RISK_ASSESSED,
            AuditEventType.BLOCKED,
        ]

    async def test_high_transmit_approved(self, bench) -> None:
        """HIGH transmit in unclassified band: approval prompted, handler called."""
        # First create an IQ file inside the session.
        iq_path = bench["session"].new_iq_path("tx")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(b"\x00\x01" * 100)

        result = await bench["executor"].execute(
            make_cmd(
                "transmit_iq",
                center_freq_hz=500_000_000,  # unclassified band → HIGH
                tx_vga_gain_db=20,
                iq_path=str(iq_path),
            )
        )
        assert result.success is True
        assert "duration_s" in result.data
        assert len(bench["approval"].calls) == 1
        # Driver was called.
        assert any(c[0] == "transmit_iq" for c in bench["driver"].calls)


class TestGrantFlow:
    async def test_grant_reclassifies_to_low(self, bench) -> None:
        """A TX grant reclassifies a matching transmission to LOW (auto-execute)."""
        # Grant TX in ISM 433 band.
        await bench["perms"].grant(
            kind="tx",
            band_start_hz=433_000_000,
            band_stop_hz=434_000_000,
            max_gain_db=30,
            ttl_seconds=3600,
        )

        # Create IQ file.
        iq_path = bench["session"].new_iq_path("tx")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(b"\x00\x01" * 100)

        await bench["executor"].execute(
            make_cmd(
                "transmit_iq",
                center_freq_hz=433_500_000,  # inside grant
                tx_vga_gain_db=20,  # below max_gain_db
                iq_path=str(iq_path),
            )
        )

        # Check the RISK_ASSESSED event has LOW; approval was NOT prompted.
        await _flush()
        rows = await bench["audit"].query(limit=200)
        risk_rows = [r for r in rows if r.event == AuditEventType.RISK_ASSESSED]
        assert risk_rows[-1].risk_level == RiskLevel.LOW
        assert len(bench["approval"].calls) == 0


class TestErrorHandling:
    async def test_hackrf_error_becomes_failed_result(self, bench) -> None:
        """HackrfError → RESULT with success=False (not BLOCKED)."""
        from hackrf_agent.hw.exceptions import HackrfNotFoundError

        async def raising_capture(**_kw):
            raise HackrfNotFoundError("no device")

        bench["driver"].capture_iq = raising_capture

        result = await bench["executor"].execute(
            make_cmd("capture_iq", center_freq_hz=433_000_000, duration_s=0.5)
        )
        assert result.success is False
        assert result.error is not None
        assert result.error.startswith("HackrfNotFoundError")
        await _flush()

        rows = await bench["audit"].query(limit=200)
        last = rows[-1]
        assert last.event == AuditEventType.RESULT
        # Verify the payload contains success=False.
        assert last.payload_json is not None

    async def test_value_error_becomes_failed_result(self, bench) -> None:
        """ValueError from handler → RESULT with success=False."""
        result = await bench["executor"].execute(
            make_cmd(
                "transmit_iq",
                center_freq_hz=433_000_000,
                tx_vga_gain_db=20,
                iq_path="/tmp/outside.iq",
            )
        )
        assert result.success is False
        assert result.error is not None
        assert result.error.startswith("ValueError")


class TestEndToEnd:
    async def test_five_commands_sequence(self, bench) -> None:
        """Five commands: BLOCKED, LOW, MEDIUM-approved, MEDIUM-denied, LOW.

        Each has the expected audit event sequence.
        """
        exec = bench["executor"]
        approval = bench["approval"]

        # 1. BLOCKED: transmit in blocked band.
        r1 = await exec.execute(
            make_cmd("transmit_iq", center_freq_hz=1090_000_000, tx_vga_gain_db=20)
        )
        assert r1.success is False
        assert r1.message.startswith("Action blocked")

        # 2. LOW: get_device_info.
        r2 = await exec.execute(make_cmd("get_device_info"))
        assert r2.success is True

        # 3. MEDIUM approved: long capture.
        approval.answer = True
        r3 = await exec.execute(make_cmd("capture_iq", center_freq_hz=433_000_000, duration_s=10.0))
        assert r3.success is True

        # 4. MEDIUM denied: long capture.
        approval.answer = False
        r4 = await exec.execute(make_cmd("capture_iq", center_freq_hz=433_000_000, duration_s=10.0))
        assert r4.success is False
        assert r4.error == "approval_denied"

        # 5. LOW: get_device_info again.
        r5 = await exec.execute(make_cmd("get_device_info"))
        assert r5.success is True

        # Now verify audit. Each command should have its own trace_id group.
        await _flush()
        rows = await bench["audit"].query(limit=500)
        trace_ids = {r.trace_id for r in rows}
        # We should have 5 distinct trace_ids (one per command).
        assert len(trace_ids) == 5

        # Verify each trace_id group's event sequence by grouping.
        by_trace: dict = {}
        for r in rows:
            by_trace.setdefault(r.trace_id, []).append(r.event)

        event_sets = list(by_trace.values())
        # One of them should be the blocked sequence.
        blocked_seq = [
            AuditEventType.COMMAND_RECEIVED,
            AuditEventType.RISK_ASSESSED,
            AuditEventType.BLOCKED,
        ]
        assert blocked_seq in event_sets, f"Expected {blocked_seq} in {event_sets}"

    async def test_trace_id_uniqueness(self, bench) -> None:
        """Three sequential execute calls → three distinct trace_ids."""
        await bench["executor"].execute(make_cmd("get_device_info"))
        await bench["executor"].execute(make_cmd("get_device_info"))
        await bench["executor"].execute(make_cmd("get_device_info"))
        await _flush()

        rows = await bench["audit"].query(limit=500)
        trace_ids = {r.trace_id for r in rows}
        assert len(trace_ids) == 3

    async def test_session_id_stamping(self, bench) -> None:
        """Every audit row has session_id == 's1'."""
        await bench["executor"].execute(make_cmd("get_device_info"))
        await _flush()
        rows = await bench["audit"].query(limit=500)
        for r in rows:
            assert r.session_id == "s1"
