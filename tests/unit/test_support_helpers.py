"""Tests for tests/support/ shared helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from hackrf_agent.ai.llm_client import LLMResponse
from hackrf_agent.domain.audit_service import AuditRow
from hackrf_agent.domain.models import AuditEventType, CommandAction, RiskLevel
from tests.support.audit_snapshot import (
    assert_snapshot_matches,
    load_snapshot,
    rows_to_snapshot,
    save_snapshot,
)
from tests.support.fake_driver import FakeDriver
from tests.support.scripted_llm import ScriptedLLMClient

# ---------------------------------------------------------------------------
# FakeDriver tests
# ---------------------------------------------------------------------------


class TestFakeDriver:
    def test_get_device_info_returns_configured_info(self) -> None:
        """FakeDriver.get_device_info() returns the configured DeviceInfo and records the call."""
        import asyncio

        async def _run():
            driver = FakeDriver()
            info = await driver.get_device_info()
            assert info.serial == "fake-serial"
            assert info.firmware_version == "0.0-fake"
            assert len(driver.calls) == 1
            assert driver.calls[0] == ("get_device_info", {})
            return info

        asyncio.run(_run())

    def test_capture_iq_writes_capture_bytes(self, tmp_path: Path) -> None:
        """FakeDriver.capture_iq(..., out_path=p) writes capture_bytes to p."""
        import asyncio

        async def _run():
            driver = FakeDriver()
            driver.capture_bytes = b"\x01\x02\x03\x04"
            out = tmp_path / "test.iq"
            result = await driver.capture_iq(out_path=out)
            assert result == out
            assert out.read_bytes() == b"\x01\x02\x03\x04"
            assert len(driver.calls) == 1
            assert driver.calls[0][0] == "capture_iq"

        asyncio.run(_run())

    def test_transmit_iq_raises_when_transmit_error_set(self) -> None:
        """transmit_iq raises transmit_error when set."""
        import asyncio

        async def _run():
            driver = FakeDriver()
            driver.transmit_error = RuntimeError("TX failed")
            with pytest.raises(RuntimeError, match="TX failed"):
                await driver.transmit_iq()
            # Call still recorded.
            assert len(driver.calls) == 1
            assert driver.calls[0][0] == "transmit_iq"

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# ScriptedLLMClient tests
# ---------------------------------------------------------------------------


class TestScriptedLLMClient:
    def test_text_entry_returns_text_response(self) -> None:
        """ScriptedLLMClient with {"type":"text","text":"hi"} returns a text response."""
        import asyncio

        async def _run():
            client = ScriptedLLMClient(
                script=[
                    {"type": "text", "text": "hi", "stop_reason": "end_turn"},
                ]
            )
            resp = await client.send(system=[], messages=[], tools=[])
            assert isinstance(resp, LLMResponse)
            assert resp.stop_reason == "end_turn"
            # Should have a text block.
            texts = [b.text for b in resp.content if b.type == "text"]
            assert texts == ["hi"]

        asyncio.run(_run())

    def test_two_entries_text_then_tool_use(self) -> None:
        """First send() returns tool_use, second returns text."""
        import asyncio

        async def _run():
            client = ScriptedLLMClient(
                script=[
                    {
                        "type": "tool_use",
                        "action": "get_device_info",
                        "args": {},
                        "justification": "Read info.",
                        "expected_effect": "Return info.",
                    },
                    {"type": "text", "text": "done"},
                ]
            )
            r1 = await client.send(system=[], messages=[], tools=[])
            assert r1.stop_reason == "tool_use"
            tool_blocks = [b for b in r1.content if b.type == "tool_use"]
            assert len(tool_blocks) == 1
            assert tool_blocks[0].input["action"] == "get_device_info"

            r2 = await client.send(system=[], messages=[], tools=[])
            assert r2.stop_reason == "end_turn"

        asyncio.run(_run())

    def test_exhausted_script_raises_index_error(self) -> None:
        """ScriptedLLMClient past end of script raises IndexError."""
        import asyncio

        async def _run():
            client = ScriptedLLMClient(
                script=[
                    {"type": "text", "text": "only one"},
                ]
            )
            await client.send(system=[], messages=[], tools=[])
            with pytest.raises(IndexError, match="script exhausted"):
                await client.send(system=[], messages=[], tools=[])

        asyncio.run(_run())

    def test_calls_recorded(self) -> None:
        """Each send() call is recorded in .calls."""
        import asyncio

        async def _run():
            client = ScriptedLLMClient(
                script=[
                    {"type": "text", "text": "a"},
                ]
            )
            await client.send(
                system="sys",
                messages=[{"role": "user", "content": "q"}],
                tools=[{"name": "t"}],
                max_tokens=100,
            )
            assert len(client.calls) == 1
            assert client.calls[0]["system"] == "sys"
            assert client.calls[0]["tools"] == [{"name": "t"}]
            assert client.calls[0]["max_tokens"] == 100

        asyncio.run(_run())

    def test_unknown_entry_type_raises(self) -> None:
        """Unknown entry type raises ValueError."""
        import asyncio

        async def _run():
            client = ScriptedLLMClient(
                script=[
                    {"type": "unknown_type"},
                ]
            )
            with pytest.raises(ValueError, match="unknown scripted entry type"):
                await client.send(system=[], messages=[], tools=[])

        asyncio.run(_run())

    def test_tool_use_with_preamble(self) -> None:
        """Tool_use entry with preamble produces both text and tool_use blocks."""
        import asyncio

        async def _run():
            client = ScriptedLLMClient(
                script=[
                    {
                        "type": "tool_use",
                        "action": "grant_list",
                        "args": {},
                        "justification": "Check grants.",
                        "expected_effect": "Return grant list.",
                        "preamble": "Let me check the grants first.",
                    }
                ]
            )
            resp = await client.send(system=[], messages=[], tools=[])
            # Should have a text block (preamble) and a tool_use block.
            texts = [b for b in resp.content if b.type == "text"]
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            assert len(texts) == 1
            assert texts[0].text == "Let me check the grants first."
            assert len(tool_uses) == 1
            assert tool_uses[0].input["action"] == "grant_list"

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# audit_snapshot tests
# ---------------------------------------------------------------------------


class TestAuditSnapshot:
    def test_rows_to_snapshot_drops_timestamps_and_uuids(self) -> None:
        """rows_to_snapshot preserves event/action/risk_level; drops timestamps/trace_ids."""
        from uuid import uuid4

        rows = [
            AuditRow(
                id=1,
                trace_id=uuid4(),
                session_id="s1",
                timestamp=1234567890.0,
                event=AuditEventType.COMMAND_RECEIVED,
                action=CommandAction.SWEEP_SPECTRUM,
                risk_level=None,
                payload_json='{"args": {}}',
                blocked_reason=None,
                duration_ms=None,
            ),
            AuditRow(
                id=2,
                trace_id=uuid4(),
                session_id="s1",
                timestamp=1234567891.0,
                event=AuditEventType.RISK_ASSESSED,
                action=CommandAction.SWEEP_SPECTRUM,
                risk_level=RiskLevel.LOW,
                payload_json='{"reason": "short RX sweep"}',
                blocked_reason=None,
                duration_ms=None,
            ),
        ]
        snap = rows_to_snapshot(rows)
        assert len(snap) == 2
        # Check shape — no timestamps, no trace_ids, no session_ids.
        for entry in snap:
            assert "event" in entry
            assert "action" in entry
            assert "risk_level" in entry
            assert "blocked_reason_present" in entry
            assert "timestamp" not in entry
            assert "trace_id" not in entry
            assert "session_id" not in entry
            assert "duration_ms" not in entry
            assert "payload_json" not in entry
        assert snap[0]["event"] == "COMMAND_RECEIVED"
        assert snap[0]["action"] == "sweep_spectrum"
        assert snap[0]["risk_level"] is None
        assert snap[1]["event"] == "RISK_ASSESSED"
        assert snap[1]["risk_level"] == "LOW"

    def test_save_and_load_snapshot_roundtrip(self, tmp_path: Path) -> None:
        """save_snapshot writes JSON; load_snapshot reads it back."""
        path = tmp_path / "snap.json"
        original = [{"event": "EXECUTED", "action": "get_device_info"}]
        save_snapshot(path, original)
        loaded = load_snapshot(path)
        assert loaded == original

    def test_assert_snapshot_matches_update_creates_and_passes(self, tmp_path: Path) -> None:
        """update=True creates a snapshot; subsequent update=False passes."""
        from uuid import uuid4

        path = tmp_path / "audit_snap.json"
        rows = [
            AuditRow(
                id=1,
                trace_id=uuid4(),
                session_id="s1",
                timestamp=1000.0,
                event=AuditEventType.EXECUTED,
                action=CommandAction.GET_DEVICE_INFO,
                risk_level=RiskLevel.LOW,
                payload_json=None,
                blocked_reason=None,
                duration_ms=42,
            ),
        ]
        # Create snapshot.
        assert_snapshot_matches(rows, path, update=True)
        assert path.is_file()
        # Verify it passes without update.
        assert_snapshot_matches(rows, path, update=False)

    def test_assert_snapshot_mismatch_raises(self, tmp_path: Path) -> None:
        """Mismatched snapshot raises AssertionError."""
        from uuid import uuid4

        path = tmp_path / "mismatch.json"
        # Pre-create one snapshot.
        save_snapshot(
            path,
            [
                {
                    "event": "EXECUTED",
                    "action": "get_device_info",
                    "risk_level": "LOW",
                    "blocked_reason_present": False,
                }
            ],
        )
        # Build rows that don't match.
        rows = [
            AuditRow(
                id=1,
                trace_id=uuid4(),
                session_id="s1",
                timestamp=1000.0,
                event=AuditEventType.BLOCKED,
                action=CommandAction.TRANSMIT_IQ,
                risk_level=RiskLevel.BLOCKED,
                payload_json=None,
                blocked_reason="ADS-B",
                duration_ms=None,
            ),
        ]
        with pytest.raises(AssertionError, match="audit snapshot mismatch"):
            assert_snapshot_matches(rows, path, update=False)

    def test_update_snapshots_env_var(self, tmp_path: Path, monkeypatch) -> None:
        """UPDATE_SNAPSHOTS=1 env var triggers update mode (no assert)."""
        from uuid import uuid4

        monkeypatch.setenv("UPDATE_SNAPSHOTS", "1")
        path = tmp_path / "env_snap.json"
        # Pre-create a different snapshot.
        save_snapshot(
            path,
            [{"event": "OLD", "action": None, "risk_level": None, "blocked_reason_present": False}],
        )
        rows = [
            AuditRow(
                id=1,
                trace_id=uuid4(),
                session_id="s1",
                timestamp=1000.0,
                event=AuditEventType.EXECUTED,
                action=CommandAction.GET_DEVICE_INFO,
                risk_level=RiskLevel.LOW,
                payload_json=None,
                blocked_reason=None,
                duration_ms=42,
            ),
        ]
        # Should update, not raise.
        assert_snapshot_matches(rows, path)  # env var makes it update
        loaded = load_snapshot(path)
        assert loaded[0]["event"] == "EXECUTED"
