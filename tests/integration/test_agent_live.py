"""Live LLM smoke test — one benign round-trip against OpenRouter.

Skipped unless ``OPENROUTER_API_KEY`` is set. Marked ``@pytest.mark.llm``.
"""

import os
from pathlib import Path

import pytest

from hackrf_agent.ai.agent import HackrfAgent
from hackrf_agent.ai.llm_client import OpenRouterClient
from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.approval import FakeApprovalPort
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.executor import CommandExecutor
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.result_formatter import ResultFormatter
from hackrf_agent.domain.risk_assessor import RiskAssessor
from hackrf_agent.domain.session import new_session
from tests.support.fake_driver import FakeDriver

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set",
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

        llm = OpenRouterClient()
        agent = HackrfAgent(llm=llm, executor=executor)

        events = []
        async for ev in agent.chat("Please read the device info and summarize it in one sentence."):
            events.append(ev)

        # Assert the loop terminated.
        assert any(e.type == "tool_call_completed" for e in events), (
            f"No tool_call_completed in events: {events}"
        )
        assert any(e.type == "turn_ended" for e in events), f"No turn_ended in events: {events}"
        assert not any(e.type == "agent_error" for e in events), (
            f"AgentError found: {[e for e in events if e.type == 'agent_error']}"
        )

        # Driver.get_device_info was called.
        assert any(c[0] == "get_device_info" for c in driver.calls), (
            f"get_device_info not called; calls: {driver.calls}"
        )
