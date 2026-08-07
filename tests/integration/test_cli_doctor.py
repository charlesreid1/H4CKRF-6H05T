"""Integration tests for ``doctor``."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from hackrf_agent.cli.main import app
from hackrf_agent.cli.settings import ENV_API_KEY


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    """Chdir into an empty dir so an ambient .env can't leak into the test."""
    d = tmp_path / "cwd"
    d.mkdir()
    monkeypatch.chdir(d)
    return d


class TestDoctor:
    """Tests for ``doctor``."""

    def test_doctor_all_ok(self, runner, home, monkeypatch, isolated_cwd) -> None:
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
        monkeypatch.setenv(ENV_API_KEY, "sk-fake")

        result = runner.invoke(
            app,
            ["--home-dir", str(home), "doctor"],
        )
        assert result.exit_code == 0, result.stderr
        assert "hackrf" in result.stdout
        assert "api_key" in result.stdout
        assert "home_dir" in result.stdout
        assert "db_schema" in result.stdout

    def test_doctor_no_hackrf(self, runner, home, monkeypatch, isolated_cwd) -> None:
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

    def test_doctor_no_api_key_is_soft_warning(
        self, runner, home, monkeypatch, isolated_cwd
    ) -> None:
        """No API key → WARN, not FAIL. The MCP server doesn't need the key;
        only `hackrf-agent chat` does. A fresh clone that only uses the MCP
        server should still exit 0 from `doctor`.
        """

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
        monkeypatch.delenv(ENV_API_KEY, raising=False)

        result = runner.invoke(
            app,
            ["--home-dir", str(home), "doctor"],
        )
        # Missing API key is now a soft warning — exit code 0 without --strict.
        assert result.exit_code == 0, result.stdout
        assert "WARN" in result.stdout
        assert "api_key" in result.stdout

    def test_doctor_readonly_home(self, runner, home, monkeypatch, isolated_cwd) -> None:
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


class TestDoctorStrict:
    """Tests for ``doctor --strict``."""

    def _mock_hackrf(self, monkeypatch):
        async def _fake_run(argv, timeout_s=60, cwd=None):
            from hackrf_agent.hw.hackrf_subprocess import SubprocessResult

            return SubprocessResult(
                argv=tuple(argv),
                returncode=0,
                stdout="hackrf_info version: 2024.02.1\n",
                stderr="",
                duration_s=0.1,
            )

        monkeypatch.setattr(
            "hackrf_agent.hw.hackrf_subprocess.run_hackrf_tool",
            _fake_run,
        )

    def test_strict_fails_when_api_key_missing(
        self, runner, home, monkeypatch, isolated_cwd
    ) -> None:
        """--strict promotes the api_key soft warning to a failure."""
        self._mock_hackrf(monkeypatch)
        monkeypatch.delenv(ENV_API_KEY, raising=False)
        result = runner.invoke(
            app, ["--home-dir", str(home), "doctor", "--strict"]
        )
        # Without --strict this exits 0; with --strict soft failures also
        # produce a non-zero exit.
        assert result.exit_code == 1, result.stdout
        assert "api_key" in result.stdout

    def test_strict_runs_extra_checks(
        self, runner, home, monkeypatch, isolated_cwd
    ) -> None:
        """--strict adds pyhackrf/firmware/corpus/records/audit_size rows."""
        self._mock_hackrf(monkeypatch)
        monkeypatch.setenv(ENV_API_KEY, "sk-fake")
        result = runner.invoke(
            app, ["--home-dir", str(home), "doctor", "--strict"]
        )
        # The extra checks may or may not pass in every env; we just
        # assert that the row names appear in the output.
        for row in ("pyhackrf", "firmware", "corpus", "records"):
            assert row in result.stdout, (
                f"Expected {row!r} in doctor --strict output; got:\n{result.stdout}"
            )
