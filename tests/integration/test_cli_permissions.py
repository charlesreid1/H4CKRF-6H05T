"""Integration tests for the ``grant`` subcommands."""

from __future__ import annotations

import re

import pytest
from typer.testing import CliRunner

from hackrf_agent.cli.main import app


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


class TestGrantTx:
    """Tests for ``grant tx``."""

    def test_grant_tx_success(self, runner, home) -> None:
        result = runner.invoke(
            app,
            [
                "--home-dir",
                str(home),
                "grant",
                "tx",
                "433.05-434.79M",
                "--for",
                "30m",
                "--max-gain",
                "20",
            ],
        )
        assert result.exit_code == 0, result.stderr
        assert "Granted" in result.stdout

    def test_grant_tx_bad_band(self, runner, home) -> None:
        result = runner.invoke(
            app,
            [
                "--home-dir",
                str(home),
                "grant",
                "tx",
                "garbage",
                "--for",
                "30m",
            ],
        )
        assert result.exit_code != 0

    def test_grant_tx_bad_duration(self, runner, home) -> None:
        result = runner.invoke(
            app,
            [
                "--home-dir",
                str(home),
                "grant",
                "tx",
                "315M",
                "--for",
                "1h30m",
            ],
        )
        assert result.exit_code != 0

    def test_grant_tx_bad_gain(self, runner, home) -> None:
        result = runner.invoke(
            app,
            [
                "--home-dir",
                str(home),
                "grant",
                "tx",
                "433.05-434.79M",
                "--for",
                "30m",
                "--max-gain",
                "999",
            ],
        )
        assert result.exit_code != 0


class TestGrantList:
    """Tests for ``grant list``."""

    def test_grant_list_empty(self, runner, home) -> None:
        result = runner.invoke(
            app,
            ["--home-dir", str(home), "grant", "list"],
        )
        assert result.exit_code == 0
        assert "No active grants" in result.stdout

    def test_grant_list_shows_grant(self, runner, home) -> None:
        # Grant a TX first.
        runner.invoke(
            app,
            [
                "--home-dir",
                str(home),
                "grant",
                "tx",
                "433.05-434.79M",
                "--for",
                "30m",
            ],
        )
        result = runner.invoke(
            app,
            ["--home-dir", str(home), "grant", "list"],
        )
        assert result.exit_code == 0, result.stderr
        assert "433050000" in result.stdout
        assert "434790000" in result.stdout


class TestGrantRevoke:
    """Tests for ``grant revoke``."""

    def test_revoke_existing(self, runner, home) -> None:
        # Grant a TX, capture the id from stdout.
        grant_result = runner.invoke(
            app,
            [
                "--home-dir",
                str(home),
                "grant",
                "tx",
                "433.05-434.79M",
                "--for",
                "30m",
            ],
        )
        assert grant_result.exit_code == 0
        # The id line looks like "id: <uuid>"
        uuid_match = re.search(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            grant_result.stdout,
        )
        assert uuid_match is not None, f"No UUID in: {grant_result.stdout}"
        grant_id = uuid_match.group(0)

        # Revoke it.
        revoke_result = runner.invoke(
            app,
            ["--home-dir", str(home), "grant", "revoke", grant_id],
        )
        assert revoke_result.exit_code == 0
        assert "Revoked" in revoke_result.stdout

        # List should be empty.
        list_result = runner.invoke(
            app,
            ["--home-dir", str(home), "grant", "list"],
        )
        assert "No active grants" in list_result.stdout

    def test_revoke_bad_uuid(self, runner, home) -> None:
        result = runner.invoke(
            app,
            ["--home-dir", str(home), "grant", "revoke", "deadbeef"],
        )
        assert result.exit_code == 2

    def test_revoke_nonexistent(self, runner, home) -> None:
        result = runner.invoke(
            app,
            [
                "--home-dir",
                str(home),
                "grant",
                "revoke",
                "12345678-1234-1234-1234-123456789012",
            ],
        )
        assert result.exit_code == 0
        assert "not found or already revoked" in result.stdout


class TestGrantRevokeAll:
    """Tests for ``grant revoke-all``."""

    def test_revoke_all_empty(self, runner, home) -> None:
        result = runner.invoke(
            app, ["--home-dir", str(home), "grant", "revoke-all"]
        )
        assert result.exit_code == 0
        assert "No active grants" in result.stdout

    def test_revoke_all_active(self, runner, home) -> None:
        # Issue two grants.
        for band in ("433.05-434.79M", "902-928M"):
            r = runner.invoke(
                app,
                [
                    "--home-dir", str(home),
                    "grant", "tx", band,
                    "--for", "30m",
                ],
            )
            assert r.exit_code == 0

        result = runner.invoke(
            app, ["--home-dir", str(home), "grant", "revoke-all"]
        )
        assert result.exit_code == 0
        assert "Revoked 2" in result.stdout

        # No active grants remain.
        list_result = runner.invoke(
            app, ["--home-dir", str(home), "grant", "list"]
        )
        assert "No active grants" in list_result.stdout
