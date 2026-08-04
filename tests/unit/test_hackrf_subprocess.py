"""Unit tests for hackrf_subprocess.py — all child processes mocked.

Never launches a real hackrf_* binary in unit tests.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from hackrf_agent.hw.exceptions import HackrfError, HackrfTimeoutError, InvalidHackrfArgError
from hackrf_agent.hw.hackrf_subprocess import SubprocessResult, run_hackrf_tool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_proc(returncode: int = 0, stdout: bytes = b"OK", stderr: bytes = b""):
    """Build an AsyncMock that mimics an asyncio subprocess."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.wait = AsyncMock()
    return proc


# ======================================================================
# argv validation
# ======================================================================


class TestArgvValidation:
    async def test_empty_argv_raises(self):
        """run_hackrf_tool([]) raises InvalidHackrfArgError."""
        with pytest.raises(InvalidHackrfArgError, match="argv is empty"):
            await run_hackrf_tool([])

    async def test_tool_not_in_allowlist_raises(self):
        """run_hackrf_tool(['rm', '-rf', '/']) raises InvalidHackrfArgError."""
        with pytest.raises(InvalidHackrfArgError, match="not in allowlist"):
            await run_hackrf_tool(["rm", "-rf", "/"])

    async def test_newline_in_arg_raises(self):
        """Control character \\n in an arg raises InvalidHackrfArgError."""
        with pytest.raises(InvalidHackrfArgError, match="control character"):
            await run_hackrf_tool(["hackrf_info", "arg\nwith\nnewline"])

    async def test_null_byte_in_arg_raises(self):
        """Null byte in an arg raises InvalidHackrfArgError."""
        with pytest.raises(InvalidHackrfArgError, match="control character"):
            await run_hackrf_tool(["hackrf_info", "\x00bad"])

    async def test_carriage_return_in_arg_raises(self):
        """\\r in an arg raises InvalidHackrfArgError."""
        with pytest.raises(InvalidHackrfArgError, match="control character"):
            await run_hackrf_tool(["hackrf_info", "bad\rthing"])

    async def test_non_string_arg_raises(self):
        """Non-string elements in argv raise InvalidHackrfArgError."""
        with pytest.raises(InvalidHackrfArgError, match="non-string"):
            await run_hackrf_tool([1, 2])


# ======================================================================
# happy path
# ======================================================================


class TestHappyPath:
    async def test_successful_run(self):
        """Happy path returns SubprocessResult with stdout decoded."""
        fake = _fake_proc(returncode=0, stdout=b"OK", stderr=b"")
        with patch("asyncio.create_subprocess_exec", return_value=fake):
            result = await run_hackrf_tool(["hackrf_info"])

        assert isinstance(result, SubprocessResult)
        assert result.returncode == 0
        assert result.stdout == "OK"
        assert result.stderr == ""
        assert result.argv == ("hackrf_info",)
        assert result.duration_s >= 0

    async def test_successful_with_args(self):
        """Happy path with extra argv elements succeeds."""
        fake = _fake_proc(returncode=0, stdout=b"data", stderr=b"")
        with patch("asyncio.create_subprocess_exec", return_value=fake):
            result = await run_hackrf_tool(["hackrf_sweep", "-1", "-f", "433:434"])

        assert result.returncode == 0
        assert result.stdout == "data"
        assert result.argv == ("hackrf_sweep", "-1", "-f", "433:434")

    async def test_hackrf_transfer_in_allowlist(self):
        """hackrf_transfer is in the allowlist."""
        fake = _fake_proc(returncode=0, stdout=b"", stderr=b"")
        with patch("asyncio.create_subprocess_exec", return_value=fake):
            result = await run_hackrf_tool(["hackrf_transfer", "-r", "capture.iq"])

        assert result.returncode == 0

    async def test_hackrf_spiflash_in_allowlist(self):
        """hackrf_spiflash is in the allowlist."""
        fake = _fake_proc(returncode=0, stdout=b"", stderr=b"")
        with patch("asyncio.create_subprocess_exec", return_value=fake):
            result = await run_hackrf_tool(["hackrf_spiflash", "-r", "firmware.bin"])

        assert result.returncode == 0


# ======================================================================
# error paths
# ======================================================================


class TestErrorPaths:
    async def test_nonzero_exit_raises_hackrferror(self):
        """Non-zero returncode raises HackrfError with stderr content."""
        fake = _fake_proc(returncode=1, stdout=b"", stderr=b"boom")
        with (
            patch("asyncio.create_subprocess_exec", return_value=fake),
            pytest.raises(HackrfError, match="boom"),
        ):
            await run_hackrf_tool(["hackrf_info"])

    async def test_timeout_raises_hackrftimeout(self):
        """A hanging child raises HackrfTimeoutError."""
        fake = _fake_proc(returncode=0)

        async def _hang() -> tuple[bytes, bytes]:
            await asyncio.sleep(9999)
            return (b"", b"")

        fake.communicate = _hang

        with (
            patch("asyncio.create_subprocess_exec", return_value=fake),
            pytest.raises(HackrfTimeoutError, match="did not exit"),
        ):
            await run_hackrf_tool(["hackrf_info"], timeout_s=0.05)

        # Verify terminate() was called.
        fake.terminate.assert_called()

    async def test_file_not_found_raises_invalid_arg(self):
        """Missing executable raises InvalidHackrfArgError."""
        with (
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=FileNotFoundError("no such file"),
            ),
            pytest.raises(InvalidHackrfArgError, match="not found on PATH"),
        ):
            await run_hackrf_tool(["hackrf_info"])

    async def test_stderr_preserved_in_error_message(self):
        """The HackrfError message includes truncated stderr."""
        long_stderr = b"x" * 500
        fake = _fake_proc(returncode=2, stderr=long_stderr)
        with patch("asyncio.create_subprocess_exec", return_value=fake):
            with pytest.raises(HackrfError) as exc_info:
                await run_hackrf_tool(["hackrf_info"])
            # stderr should be truncated to ~400 chars.
            assert len(exc_info.value.args[0]) < 600
            assert "xxxx" in exc_info.value.args[0]
