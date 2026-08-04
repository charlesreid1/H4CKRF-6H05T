"""Live-LLM smoke test for the ``chat`` command.

Requires BOTH a HackRF attached AND an OpenRouter API key.
Always skipped in CI.
"""

from __future__ import annotations

import os

import pytest
from typer.testing import CliRunner

from hackrf_agent.cli.main import app

pytestmark = pytest.mark.llm


@pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set",
)
@pytest.mark.hardware
def test_chat_smoke(tmp_path):
    """End-to-end: launch chat, send one message, verify tool call + reply.

    Feeds stdin via CliRunner.invoke(input=...). Requires HackRF + API key.
    """
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    runner = CliRunner()

    # Store API key into the test keychain backend first.
    api_key = os.environ["OPENROUTER_API_KEY"]
    from hackrf_agent.cli.settings import SettingsService

    svc = SettingsService(home_dir=home)
    svc.set_api_key(api_key)

    result = runner.invoke(
        app,
        ["--home-dir", str(home), "chat"],
        input="Read the device info.\n/quit\n",
    )
    # Chat should exit cleanly.
    assert result.exit_code == 0, result.stderr
    # Should contain at least a tool call and an agent reply.
    output = result.stdout
    assert "→ tool" in output or "← ok" in output, (
        f"Expected tool call in output, got:\n{output[:500]}"
    )
    assert "agent" in output, f"Expected agent reply in output, got:\n{output[:500]}"
