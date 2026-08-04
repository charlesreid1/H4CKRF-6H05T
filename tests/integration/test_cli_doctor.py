"""Integration tests for ``doctor`` and ``set-api-key``."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from hackrf_agent.cli.main import app
from hackrf_agent.cli.settings import SettingsService


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


class TestDoctor:
    """Tests for ``doctor``."""

    def test_doctor_all_ok(self, runner, home, monkeypatch) -> None:
        """With hackrf_info mocked to succeed and api key set, all OK."""

        # Mock hackrf_info to succeed.
        async def _fake_run(argv, timeout_s=60, cwd=None):
            from hackrf_agent.hw.hackrf_subprocess import SubprocessResult

            return SubprocessResult(
                argv=tuple(argv),
                returncode=0,
                stdout="HackRF One Info\n...",
                stderr="",
                duration_s=0.1,
            )

        monkeypatch.setattr(
            "hackrf_agent.hw.hackrf_subprocess.run_hackrf_tool",
            _fake_run,
        )
        # Mock API key as present.
        monkeypatch.setattr(
            SettingsService,
            "get_api_key",
            lambda self: "sk-fake",
        )

        result = runner.invoke(
            app,
            ["--home-dir", str(home), "doctor"],
        )
        assert result.exit_code == 0, result.stderr
        assert "hackrf" in result.stdout
        assert "api_key" in result.stdout
        assert "home_dir" in result.stdout
        assert "db_schema" in result.stdout

    def test_doctor_no_hackrf(self, runner, home, monkeypatch) -> None:
        """hackrf_info missing → FAIL on hackrf check."""
        from hackrf_agent.hw.exceptions import InvalidHackrfArgError

        async def _fake_run(argv, timeout_s=60, cwd=None):
            raise InvalidHackrfArgError("not found")

        monkeypatch.setattr(
            "hackrf_agent.hw.hackrf_subprocess.run_hackrf_tool",
            _fake_run,
        )

        result = runner.invoke(
            app,
            ["--home-dir", str(home), "doctor"],
        )
        assert result.exit_code == 1
        assert "FAIL" in result.stdout

    def test_doctor_no_api_key(self, runner, home, monkeypatch) -> None:
        """No API key → FAIL on api_key check."""

        # Mock hackrf_info to succeed.
        async def _fake_run(argv, timeout_s=60, cwd=None):
            from hackrf_agent.hw.hackrf_subprocess import SubprocessResult

            return SubprocessResult(
                argv=tuple(argv),
                returncode=0,
                stdout="HackRF One Info\n...",
                stderr="",
                duration_s=0.1,
            )

        monkeypatch.setattr(
            "hackrf_agent.hw.hackrf_subprocess.run_hackrf_tool",
            _fake_run,
        )
        # No API key set.
        monkeypatch.setattr(
            SettingsService,
            "get_api_key",
            lambda self: None,
        )

        result = runner.invoke(
            app,
            ["--home-dir", str(home), "doctor"],
        )
        assert result.exit_code == 1
        assert "FAIL" in result.stdout
        assert "api_key" in result.stdout

    def test_doctor_readonly_home(self, runner, home, monkeypatch) -> None:
        """Read-only home dir → FAIL."""

        # Prevent mkdir.
        def _failing_mkdir(self, *a, **kw):
            raise OSError("Permission denied")

        monkeypatch.setattr(type(home), "mkdir", _failing_mkdir)

        result = runner.invoke(
            app,
            ["--home-dir", str(home), "doctor"],
        )
        assert result.exit_code == 1
        assert "FAIL" in result.stdout
        assert "home_dir" in result.stdout


class TestSetApiKey:
    """Tests for ``set-api-key``."""

    def test_set_api_key(self, runner, home, monkeypatch) -> None:
        """set-api-key --key stores the key."""
        # Mock keyring to avoid touching the real OS keychain.
        store: dict[tuple[str, str], str] = {}

        def _set(service, user, val):
            store[(service, user)] = val

        def _get(service, user):
            return store.get((service, user))

        monkeypatch.setattr("keyring.set_password", _set)
        monkeypatch.setattr("keyring.get_password", _get)

        result = runner.invoke(
            app,
            [
                "--home-dir",
                str(home),
                "set-api-key",
                "--key",
                "sk-real-key-value",
            ],
        )
        assert result.exit_code == 0, result.stderr
        assert "API key stored" in result.stdout
        # Verify via the direct get_api_key method (which uses our mocked keyring).
        svc = SettingsService(home_dir=home)
        assert svc.get_api_key() == "sk-real-key-value"
