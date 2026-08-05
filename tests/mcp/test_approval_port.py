"""Unit tests for McpApprovalPort — elicitation round-trip; timeout; decline.

The port reads the MCP session from a ContextVar (set by server.py's
on_call_tool handler). Tests mock the session's ``elicit()`` method and
set the ContextVar to simulate the handler context.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from hackrf_agent.domain.models import (
    CommandAction,
    ExecuteCommand,
    RiskAssessment,
    RiskLevel,
)
from hackrf_agent.mcp.approval_port import McpApprovalPort, _current_session


def _make_command(
    action: CommandAction = CommandAction.TRANSMIT_IQ,
    justification: str = "test",
    expected_effect: str = "test",
) -> ExecuteCommand:
    return ExecuteCommand(
        action=action,
        args={"center_freq_hz": 433_000_000, "tx_vga_gain_db": 10, "iq_path": "/tmp/test.iq"},
        justification=justification,
        expected_effect=expected_effect,
    )


def _make_medium_risk() -> RiskAssessment:
    return RiskAssessment(
        level=RiskLevel.MEDIUM,
        reason="test medium",
        requires_confirmation=True,
    )


def _make_high_risk() -> RiskAssessment:
    return RiskAssessment(
        level=RiskLevel.HIGH,
        reason="test high",
        requires_confirmation=True,
    )


# ElicitResult is a pydantic model with action + content.
class _FakeElicitResult:
    """Minimal stand-in for mcp.types.ElicitResult."""

    def __init__(self, action: str, content: dict | None = None) -> None:
        self.action = action
        self.content = content or {}


@pytest.fixture
def mock_session() -> AsyncMock:
    """Return a mock ServerSession whose elicit() returns accept.

    MEDIUM elicitations carry no form fields — accept alone means approve.
    HIGH-specific tests override the return_value.
    """
    session = AsyncMock()
    session.elicit.return_value = _FakeElicitResult(action="accept", content={})
    return session


@pytest.fixture(autouse=True)
def _clear_contextvar() -> None:
    """Reset the ContextVar before each test."""
    _current_session.set(None)
    yield
    _current_session.set(None)


class TestMcpApprovalPortElicitation:
    """Happy-path approvals via the real session.elicit() interface."""

    async def test_medium_approved(self, mock_session: AsyncMock) -> None:
        _current_session.set(mock_session)
        port = McpApprovalPort()
        cmd = _make_command()
        risk = _make_medium_risk()
        assert await port.request(cmd, risk) is True
        mock_session.elicit.assert_called_once()

    async def test_high_approved_on_accept(self, mock_session: AsyncMock) -> None:
        # HIGH uses the same accept-is-approval flow as MEDIUM.
        _current_session.set(mock_session)
        port = McpApprovalPort()
        cmd = _make_command()
        risk = _make_high_risk()
        assert await port.request(cmd, risk) is True

    async def test_high_denied_on_decline(self, mock_session: AsyncMock) -> None:
        mock_session.elicit.return_value = _FakeElicitResult(action="decline", content={})
        _current_session.set(mock_session)
        port = McpApprovalPort()
        cmd = _make_command()
        risk = _make_high_risk()
        assert await port.request(cmd, risk) is False

    async def test_denied_when_action_is_decline(self, mock_session: AsyncMock) -> None:
        mock_session.elicit.return_value = _FakeElicitResult(
            action="decline", content={}
        )
        _current_session.set(mock_session)
        port = McpApprovalPort()
        cmd = _make_command()
        risk = _make_medium_risk()
        assert await port.request(cmd, risk) is False

    async def test_denied_when_action_is_cancel(self, mock_session: AsyncMock) -> None:
        mock_session.elicit.return_value = _FakeElicitResult(
            action="cancel", content={}
        )
        _current_session.set(mock_session)
        port = McpApprovalPort()
        cmd = _make_command()
        risk = _make_medium_risk()
        assert await port.request(cmd, risk) is False

    async def test_denied_when_elicit_returns_none(self, mock_session: AsyncMock) -> None:
        mock_session.elicit.return_value = None
        _current_session.set(mock_session)
        port = McpApprovalPort()
        cmd = _make_command()
        risk = _make_medium_risk()
        assert await port.request(cmd, risk) is False

    async def test_denied_when_elicit_raises(self, mock_session: AsyncMock) -> None:
        mock_session.elicit.side_effect = RuntimeError("host disconnected")
        _current_session.set(mock_session)
        port = McpApprovalPort()
        cmd = _make_command()
        risk = _make_medium_risk()
        assert await port.request(cmd, risk) is False

    async def test_auto_approve_medium_skips_elicit(self, mock_session: AsyncMock) -> None:
        _current_session.set(mock_session)
        port = McpApprovalPort(auto_approve_medium=True)
        cmd = _make_command()
        risk = _make_medium_risk()
        assert await port.request(cmd, risk) is True
        mock_session.elicit.assert_not_called()

    async def test_auto_approve_does_not_skip_high(self, mock_session: AsyncMock) -> None:
        # HIGH must still elicit even when MEDIUM is auto-approved.
        _current_session.set(mock_session)
        port = McpApprovalPort(auto_approve_medium=True)
        cmd = _make_command()
        risk = _make_high_risk()
        assert await port.request(cmd, risk) is True
        mock_session.elicit.assert_called_once()

    async def test_no_session_returns_false(self) -> None:
        _current_session.set(None)
        port = McpApprovalPort()
        cmd = _make_command()
        risk = _make_medium_risk()
        assert await port.request(cmd, risk) is False


class TestElicitationMessage:
    """The formatted message contains key fields."""

    def test_message_includes_action_and_risk(self) -> None:
        cmd = _make_command()
        risk = RiskAssessment(
            level=RiskLevel.HIGH,
            reason="amateur band TX",
            requires_confirmation=True,
        )
        msg = McpApprovalPort._format_message(cmd, risk)
        assert "transmit_iq" in msg
        assert "HIGH" in msg
        assert "amateur band TX" in msg
        assert "test" in msg  # justification

    def test_elicitation_schema_for_medium(self) -> None:
        # No form fields — accept alone means approve. Host renders a
        # plain Allow/Deny prompt.
        risk = RiskAssessment(
            level=RiskLevel.MEDIUM,
            reason="test",
            requires_confirmation=True,
        )
        schema = McpApprovalPort._elicitation_schema(risk)
        assert schema["properties"] == {}
        assert "required" not in schema

    def test_elicitation_schema_for_high(self) -> None:
        # HIGH uses the same empty schema as MEDIUM; the tier is signaled
        # via the message text, not the form shape.
        risk = RiskAssessment(
            level=RiskLevel.HIGH,
            reason="test",
            requires_confirmation=True,
        )
        schema = McpApprovalPort._elicitation_schema(risk)
        assert schema["properties"] == {}
        assert "required" not in schema
