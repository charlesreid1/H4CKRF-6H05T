"""End-to-end: the full keyfob-hunt from plan-bender.md encoded as an executable test.

Every step is asserted. Uses ScriptedLLMClient + FakeDriver + real executor +
real audit DB.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from hackrf_agent.ai.agent import (
    AgentError,
    HackrfAgent,
    ToolCallStarted,
    TurnEnded,
)
from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.approval import FakeApprovalPort
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.executor import CommandExecutor
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.result_formatter import ResultFormatter
from hackrf_agent.domain.risk_assessor import RiskAssessor
from hackrf_agent.domain.session import new_session
from tests.support.audit_snapshot import assert_snapshot_matches
from tests.support.fake_driver import FakeDriver
from tests.support.scripted_llm import ScriptedLLMClient

SNAPSHOT_PATH = Path(__file__).parent.parent / "fixtures" / "audit" / "keyfob_session.json"


def _sweep_result_with_peak_at(freq_hz: float, sample_rate: int = 2_000_000):
    """Build a synthetic sweep result with a single strong peak."""
    fft_size = 4096
    freqs = np.linspace(
        freq_hz - sample_rate / 2, freq_hz + sample_rate / 2, fft_size,
    ).astype(np.float64)
    spec = np.full(fft_size, -90.0, dtype=np.float32)  # noise floor
    peak_bin = fft_size // 2
    spec[peak_bin] = -45.0
    return spec, freqs


def _sweep_result_noise_only(center_hz: float, sample_rate: int = 2_000_000):
    fft_size = 4096
    freqs = np.linspace(
        center_hz - sample_rate / 2, center_hz + sample_rate / 2, fft_size,
    ).astype(np.float64)
    spec = np.full(fft_size, -90.0, dtype=np.float32)
    return spec, freqs


async def test_keyfob_workflow(tmp_path):
    """End-to-end: the full keyfob-hunt from plan-bender.md.

    Asserts:
      - Correct sequence of tool calls (sweep 315, sweep 433, capture 433).
      - MEDIUM capture prompted approval exactly once.
      - Audit trail matches the committed snapshot.
      - No hardware imports leaked (would fail on import if pyhackrf missing).
    """
    db = tmp_path / "agent.db"
    await ensure_schema(db)
    session_paths = new_session(tmp_path / "sessions")

    # Driver returns noise for the 315 sweep, a peak for the 433 sweep.
    driver = FakeDriver()

    async def sweep_router(**kw):
        driver.calls.append(("sweep_spectrum", kw))
        if kw["start_hz"] < 400_000_000:
            return _sweep_result_noise_only((kw["start_hz"] + kw["stop_hz"]) / 2)
        return _sweep_result_with_peak_at(433_925_000)

    driver.sweep_spectrum = sweep_router

    approval = FakeApprovalPort(answer=True)
    llm = ScriptedLLMClient(script=[
        # Turn 1: sweep ISM 315
        {"type": "tool_use", "action": "sweep_spectrum",
         "args": {"start_freq_hz": 314_000_000, "end_freq_hz": 316_000_000,
                  "sample_rate_hz": 2_000_000, "dwell_s": 0.1},
         "justification": "Scan US ISM 315 first; keyfobs typically 315 or 433.",
         "expected_effect": "Return peak bins over 314-316 MHz."},
        # Turn 2: sweep ISM 433
        {"type": "tool_use", "action": "sweep_spectrum",
         "args": {"start_freq_hz": 433_000_000, "end_freq_hz": 434_000_000,
                  "sample_rate_hz": 2_000_000, "dwell_s": 0.1},
         "justification": "315 was noise floor only; try 433.",
         "expected_effect": "Return peak bins over 433-434 MHz."},
        # Turn 3: capture at 433.925 for 6 s (MEDIUM — > 5 s)
        {"type": "tool_use", "action": "capture_iq",
         "args": {"center_freq_hz": 433_925_000, "sample_rate_hz": 2_000_000,
                  "duration_s": 6.0, "lna_gain_db": 16},
         "justification": "Peak at 433.925 MHz; capture 6 s to try to demod rolling code.",
         "expected_effect": "Save 12M-sample IQ; return summary."},
        # Turn 4: wrap up
        {"type": "text", "text": "Found the keyfob at 433.925 MHz. Capture saved."},
    ])
    async with AuditService(db) as audit:
        executor = CommandExecutor(
            session_id="keyfob-e2e",
            risk_assessor=RiskAssessor(),
            permissions=PermissionService(db),
            audit=audit,
            driver=driver,
            formatter=ResultFormatter(),
            approval=approval,
            session_paths=session_paths,
        )
        agent = HackrfAgent(
            llm=llm, executor=executor,
        )
        events = [ev async for ev in agent.chat("Find my car's keyfob frequency.")]

        # ---- Structural assertions ----
        sweep_events = [e for e in events if isinstance(e, ToolCallStarted)
                        and e.action == "sweep_spectrum"]
        capture_events = [e for e in events if isinstance(e, ToolCallStarted)
                          and e.action == "capture_iq"]
        assert len(sweep_events) == 2
        assert len(capture_events) == 1

        # ---- Approval was prompted exactly once (the MEDIUM capture) ----
        assert len(approval.calls) == 1
        assert approval.calls[0][0].action.value == "capture_iq"

        # ---- Terminates cleanly ----
        assert isinstance(events[-1], TurnEnded)
        assert events[-1].stop_reason == "end_turn"
        assert not any(isinstance(e, AgentError) for e in events)

        # ---- Audit snapshot ----
        rows = await audit.query(session_id="keyfob-e2e", limit=1000)
        assert_snapshot_matches(rows, SNAPSHOT_PATH)
