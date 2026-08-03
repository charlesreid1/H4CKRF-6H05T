"""Tests for approval.py — ApprovalPort protocol and test doubles."""

import asyncio

import pytest

from hackrf_agent.domain.approval import (
    AlwaysAllowApprovalPort,
    ApprovalPort,
    FakeApprovalPort,
)
from hackrf_agent.domain.models import (
    CommandAction,
    ExecuteCommand,
    RiskAssessment,
    RiskLevel,
)


@pytest.fixture
def cmd() -> ExecuteCommand:
    return ExecuteCommand(
        action=CommandAction.GET_DEVICE_INFO,
        justification="test",
        expected_effect="test",
    )


@pytest.fixture
def risk_low() -> RiskAssessment:
    return RiskAssessment(level=RiskLevel.LOW, reason="test")


@pytest.fixture
def risk_high() -> RiskAssessment:
    return RiskAssessment(level=RiskLevel.HIGH, reason="test", requires_confirmation=True)


def _run(coro):
    """Run a coroutine synchronously — helper for testing async methods."""
    return asyncio.run(coro)


class TestFakeApprovalPort:
    def test_answer_true(self, cmd: ExecuteCommand, risk_low: RiskAssessment) -> None:
        """FakeApprovalPort(answer=True) returns True and records the call."""
        port = FakeApprovalPort(answer=True)
        result = _run(port.request(cmd, risk_low))

        assert result is True
        assert len(port.calls) == 1
        assert port.calls[0] == (cmd, risk_low)

    def test_answer_false(self, cmd: ExecuteCommand, risk_low: RiskAssessment) -> None:
        """FakeApprovalPort(answer=False) returns False."""
        port = FakeApprovalPort(answer=False)
        result = _run(port.request(cmd, risk_low))

        assert result is False
        assert len(port.calls) == 1

    def test_answers_sequence(self, cmd: ExecuteCommand, risk_low: RiskAssessment) -> None:
        """FakeApprovalPort(answers=[...]) returns each in order."""
        port = FakeApprovalPort(answers=[True, False, True])
        assert _run(port.request(cmd, risk_low)) is True
        assert _run(port.request(cmd, risk_low)) is False
        assert _run(port.request(cmd, risk_low)) is True
        assert len(port.calls) == 3

    def test_answers_empty_falls_back_to_answer(
        self, cmd: ExecuteCommand, risk_low: RiskAssessment
    ) -> None:
        """When answers list is exhausted, falls back to answer."""
        port = FakeApprovalPort(answer=False, answers=[True])
        assert _run(port.request(cmd, risk_low)) is True
        assert _run(port.request(cmd, risk_low)) is False


class TestAlwaysAllowApprovalPort:
    def test_always_returns_true(self, cmd: ExecuteCommand, risk_high: RiskAssessment) -> None:
        """AlwaysAllowApprovalPort returns True regardless of risk level."""
        port = AlwaysAllowApprovalPort()
        assert _run(port.request(cmd, risk_high)) is True

    def test_satisfies_protocol(self) -> None:
        """AlwaysAllowApprovalPort structurally satisfies ApprovalPort."""
        port = AlwaysAllowApprovalPort()
        assert isinstance(port, ApprovalPort)

    def test_fake_satisfies_protocol(self) -> None:
        """FakeApprovalPort structurally satisfies ApprovalPort."""
        port = FakeApprovalPort()
        assert isinstance(port, ApprovalPort)
