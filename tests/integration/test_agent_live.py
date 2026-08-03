"""Live LLM smoke test — one benign round-trip against real Claude.

Skipped unless ``ANTHROPIC_API_KEY`` is set. Marked ``@pytest.mark.llm``.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

from hackrf_agent.ai.agent import HackrfAgent
from hackrf_agent.ai.llm_client import AnthropicClient
from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.approval import FakeApprovalPort
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.executor import CommandExecutor
from hackrf_agent.domain.models import DeviceInfo
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.result_formatter import ResultFormatter
from hackrf_agent.domain.risk_assessor import RiskAssessor
from hackrf_agent.domain.session import new_session

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# FakeDriver
# ---------------------------------------------------------------------------


@dataclass
class FakeDriver:
    device_info: DeviceInfo = field(
        default_factory=lambda: DeviceInfo("s", "fw", "r1", "pid")
    )
    calls: list[tuple[str, dict]] = field(default_factory=list)
    sweep_result: tuple = field(
        default_factory=lambda: (
            np.zeros(4096, dtype=np.float32),
            np.arange(4096, dtype=np.float64),
        )
    )
    capture_bytes: bytes = b"\x00\x00" * 1024

    async def get_device_info(self):
        self.calls.append(("get_device_info", {}))
        return self.device_info

    async def sweep_spectrum(self, **kw):
        self.calls.append(("sweep_spectrum", kw))
        return self.sweep_result

    async def capture_iq(self, *, out_path, **kw):
        self.calls.append(("capture_iq", {"out_path": out_path, **kw}))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(self.capture_bytes)
        return out_path

    async def transmit_iq(self, **kw):
        self.calls.append(("transmit_iq", kw))


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
async def test_live_get_device_info(tmp_path: Path) -> None:
    """One benign round-trip against real Claude with a fake driver.

    We don't assert on the exact wording of the model's reply — that's
    non-deterministic. We only assert:
      - the loop terminates (stop_reason=end_turn eventually)
      - driver.get_device_info was called
      - no AgentError yielded
    """
    db = tmp_path / "agent.db"
    await ensure_schema(db)

    driver = FakeDriver()
    approval = FakeApprovalPort(answer=True)
    perms = PermissionService(db)

    async with AuditService(db) as audit:
        session = new_session(tmp_path / "sessions")
        executor = CommandExecutor(
            session_id="live_s1",
            risk_assessor=RiskAssessor(),
            permissions=perms,
            audit=audit,
            driver=driver,
            formatter=ResultFormatter(),
            approval=approval,
            session_paths=session,
        )

        llm = AnthropicClient()
        agent = HackrfAgent(llm=llm, executor=executor, permissions=perms)

        events = []
        async for ev in agent.chat(
            "Please read the device info and summarize it in one sentence."
        ):
            events.append(ev)

        # Assert the loop terminated.
        assert any(e.type == "tool_call_completed" for e in events), (
            f"No tool_call_completed in events: {events}"
        )
        assert any(e.type == "turn_ended" for e in events), (
            f"No turn_ended in events: {events}"
        )
        assert not any(e.type == "agent_error" for e in events), (
            f"AgentError found: {[e for e in events if e.type == 'agent_error']}"
        )

        # Driver.get_device_info was called.
        assert any(c[0] == "get_device_info" for c in driver.calls), (
            f"get_device_info not called; calls: {driver.calls}"
        )
