"""Unit tests for :mod:`hackrf_agent.cli.approval`."""

from __future__ import annotations

import pytest
from rich.console import Console

from hackrf_agent.cli.approval import CliApprovalPort
from hackrf_agent.domain.models import (
    CommandAction,
    ExecuteCommand,
    RiskAssessment,
    RiskLevel,
)


def make_cmd(action: CommandAction = CommandAction.CAPTURE_IQ) -> ExecuteCommand:
    return ExecuteCommand(
        action=action,
        args={"duration_s": 10.0},
        justification="test justification",
        expected_effect="test effect",
    )


def make_risk(level: RiskLevel) -> RiskAssessment:
    return RiskAssessment(
        level=level,
        reason="test reason",
        requires_confirmation=(level != RiskLevel.LOW),
    )


@pytest.fixture
def quiet_console():
    """A Console that writes to /dev/null so tests don't spew output."""
    with open("/dev/null", "w") as f:
        yield Console(file=f, force_terminal=False)


class TestCliApprovalPortMedium:
    """Tests for MEDIUM-risk approval."""

    @pytest.mark.asyncio
    async def test_auto_approve_medium_skips_prompt(self, quiet_console, monkeypatch) -> None:
        port = CliApprovalPort(console=quiet_console, auto_approve_medium=True)
        # Confirm.ask should NOT be called.
        ask_was_called = False

        def _fake_ask(*a, **kw):
            nonlocal ask_was_called
            ask_was_called = True
            return True

        monkeypatch.setattr("rich.prompt.Confirm.ask", _fake_ask)
        result = await port.request(make_cmd(), make_risk(RiskLevel.MEDIUM))
        assert result is True
        assert not ask_was_called

    @pytest.mark.asyncio
    async def test_medium_user_approves(self, quiet_console, monkeypatch) -> None:
        port = CliApprovalPort(console=quiet_console)
        monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *a, **kw: True)
        result = await port.request(make_cmd(), make_risk(RiskLevel.MEDIUM))
        assert result is True

    @pytest.mark.asyncio
    async def test_medium_user_denies(self, quiet_console, monkeypatch) -> None:
        port = CliApprovalPort(console=quiet_console)
        monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *a, **kw: False)
        result = await port.request(make_cmd(), make_risk(RiskLevel.MEDIUM))
        assert result is False


class TestCliApprovalPortHigh:
    """Tests for HIGH-risk approval."""

    @pytest.mark.asyncio
    async def test_high_confirm_exact(self, quiet_console, monkeypatch) -> None:
        port = CliApprovalPort(console=quiet_console)
        monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *a, **kw: "CONFIRM")
        result = await port.request(make_cmd(), make_risk(RiskLevel.HIGH))
        assert result is True

    @pytest.mark.asyncio
    async def test_high_confirm_lowercase_denied(self, quiet_console, monkeypatch) -> None:
        port = CliApprovalPort(console=quiet_console)
        monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *a, **kw: "confirm")
        result = await port.request(make_cmd(), make_risk(RiskLevel.HIGH))
        assert result is False

    @pytest.mark.asyncio
    async def test_high_other_string_denied(self, quiet_console, monkeypatch) -> None:
        port = CliApprovalPort(console=quiet_console)
        monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *a, **kw: "y")
        result = await port.request(make_cmd(), make_risk(RiskLevel.HIGH))
        assert result is False

    @pytest.mark.asyncio
    async def test_high_auto_approve_does_not_skip_prompt(self, quiet_console, monkeypatch) -> None:
        """auto_approve_medium=True does NOT extend to HIGH-risk commands."""
        port = CliApprovalPort(console=quiet_console, auto_approve_medium=True)
        prompt_was_called = False

        def _fake_prompt(*a, **kw):
            nonlocal prompt_was_called
            prompt_was_called = True
            return "CONFIRM"

        monkeypatch.setattr("rich.prompt.Prompt.ask", _fake_prompt)
        result = await port.request(make_cmd(), make_risk(RiskLevel.HIGH))
        assert result is True
        assert prompt_was_called
