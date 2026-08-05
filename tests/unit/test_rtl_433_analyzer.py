"""Unit tests for hw/rtl_433_analyzer.py — mock subprocess, assert argv and parsing."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from hackrf_agent.hw.exceptions import Rtl433Failed, Rtl433NotInstalled
from hackrf_agent.hw.rtl_433_analyzer import analyze


# ---------------------------------------------------------------------------
# Canned fixtures
# ---------------------------------------------------------------------------

_MATCHES_JSON = json.dumps({"model": "Acurite-606TX", "id": 42, "channel": "A"})
_STDERR_WITH_PULSES = (
    "pulse_width: min 200, max 600, median 400\n"
    "Guessing modulation: PWM\n"
)
_STDERR_NO_MOD = "pulse_width: min 200, max 600, median 400\n"


def _fake_proc(stdout: bytes, stderr: bytes, returncode: int = 0):
    """Return an AsyncMock that mimics a completed asyncio subprocess."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAnalyzeHappyPath:
    async def test_parses_matches_and_pulses(self) -> None:
        """Protocol matches in stdout + pulse stats in stderr → both parsed."""
        proc = _fake_proc(
            stdout=_MATCHES_JSON.encode(),
            stderr=_STDERR_WITH_PULSES.encode(),
        )
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtl_433"),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=proc,
            ) as spawn_mock,
        ):
            result = await analyze(Path("/tmp/test.iq"), 2_000_000)

        # argv shape
        argv = spawn_mock.call_args[0]
        assert argv[0] == "/usr/local/bin/rtl_433"
        assert "-r" in argv
        assert "-s" in argv
        assert "2000000" in argv
        assert "-f" in argv and "cs8" in argv
        assert "-A" in argv
        assert "-F" in argv and "json" in argv
        assert "-M" in argv and "level" in argv

        # parsed output
        assert result["modulation_guess"] == "PWM"
        assert result["pulse_stats"] == {"min_us": 200, "max_us": 600, "median_us": 400}
        assert len(result["protocol_matches"]) == 1
        assert result["protocol_matches"][0]["model"] == "Acurite-606TX"

    async def test_no_protocol_matches(self) -> None:
        """rtl_433 returns empty stdout → empty matches list, still parses stderr."""
        proc = _fake_proc(stdout=b"", stderr=_STDERR_WITH_PULSES.encode(), returncode=1)
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtl_433"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            result = await analyze(Path("/tmp/test.iq"), 2_000_000)
        assert result["protocol_matches"] == []
        assert result["modulation_guess"] == "PWM"

    async def test_empty_stderr(self) -> None:
        """No modulation guess in stderr → defaults to 'unknown'."""
        proc = _fake_proc(stdout=b"", stderr=b"", returncode=1)
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtl_433"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            result = await analyze(Path("/tmp/test.iq"), 2_000_000)
        assert result["modulation_guess"] == "unknown"
        assert result["pulse_stats"] is None

    async def test_no_mod_in_stderr(self) -> None:
        """Pulse stats present but no modulation guess line."""
        proc = _fake_proc(stdout=b"", stderr=_STDERR_NO_MOD.encode(), returncode=1)
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtl_433"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            result = await analyze(Path("/tmp/test.iq"), 2_000_000)
        assert result["modulation_guess"] == "unknown"
        assert result["pulse_stats"] is not None


class TestAnalyzeErrorPaths:
    async def test_not_installed(self) -> None:
        """shutil.which returns None → Rtl433NotInstalled."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(Rtl433NotInstalled, match="brew install"):
                await analyze(Path("/tmp/test.iq"), 2_000_000)

    async def test_unexpected_returncode(self) -> None:
        """Return code 2 → Rtl433Failed with truncated stderr."""
        proc = _fake_proc(stdout=b"", stderr=b"some error", returncode=2)
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtl_433"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            with pytest.raises(Rtl433Failed, match="some error"):
                await analyze(Path("/tmp/test.iq"), 2_000_000)

    async def test_timeout(self) -> None:
        """Subprocess hangs → Rtl433Failed after timeout."""
        proc = AsyncMock()
        proc.communicate = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtl_433"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            with pytest.raises(Rtl433Failed, match="timed out"):
                await analyze(Path("/tmp/test.iq"), 2_000_000, timeout_s=0.1)
        proc.kill.assert_called_once()
