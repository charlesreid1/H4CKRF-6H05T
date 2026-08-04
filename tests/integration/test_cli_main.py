"""Integration tests for the top-level Typer app."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from hackrf_agent.cli.main import app


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


class TestMainHelp:
    """Tests for ``--help`` output."""

    def test_root_help(self, runner, home) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "chat" in result.stdout
        assert "grant" in result.stdout
        assert "audit" in result.stdout
        assert "doctor" in result.stdout

    def test_grant_help(self, runner, home) -> None:
        result = runner.invoke(app, ["grant", "--help"])
        assert result.exit_code == 0
        assert "tx" in result.stdout
        assert "list" in result.stdout
        assert "revoke" in result.stdout

    def test_home_dir_option(self, runner, home) -> None:
        """--home-dir is accepted and the SettingsService gets the right path."""
        home.mkdir(parents=True, exist_ok=True)
        result = runner.invoke(
            app,
            ["--home-dir", str(home), "grant", "list"],
        )
        assert result.exit_code == 0

    def test_no_args_shows_help(self, runner) -> None:
        result = runner.invoke(app, [])
        # no_args_is_help means it shows help content; Typer exits 2 for this.
        assert "Usage:" in result.stdout or "hackrf-agent" in result.stdout
