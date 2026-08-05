"""Unit tests for hw/urh_demodulator.py — mock subprocess, assert argv and temp file cleanup."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from hackrf_agent.hw.exceptions import UrhFailed, UrhNotInstalled
from hackrf_agent.hw.urh_demodulator import _cs8_to_complex_bytes, demodulate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_proc(stdout: bytes, stderr: bytes, returncode: int = 0):
    """Return an AsyncMock that mimics a completed asyncio subprocess."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


def _tiny_cs8_bytes() -> bytes:
    """Enough int8 IQ for the converter to work (128 samples)."""
    import numpy as np

    arr = np.zeros(256, dtype=np.int8)  # 128 IQ pairs
    return arr.tobytes()


# ---------------------------------------------------------------------------
# Conversion tests
# ---------------------------------------------------------------------------


class TestCs8ToComplex:
    def test_output_byte_count(self) -> None:
        """float32 output is exactly 4× the int8 input size."""
        raw = b"\x00\x01" * 100  # 200 bytes = 100 IQ pairs
        out = _cs8_to_complex_bytes(raw)
        assert len(out) == 800  # 200 * 4 (float32)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestDemodulateHappyPath:
    async def test_basic_ask_demod(self, tmp_path: Path) -> None:
        """Basic ASK demod with canned bit output."""
        iq_path = tmp_path / "test.iq"
        iq_path.write_bytes(_tiny_cs8_bytes())

        canned_bits = b"1010110001111000\n"
        proc = _fake_proc(stdout=canned_bits, stderr=b"")
        with (
            patch("shutil.which", return_value="/usr/local/bin/urh_cli"),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=proc,
            ) as spawn_mock,
        ):
            result = await demodulate(
                iq_path, 2_000_000, "ASK", samples_per_symbol=500
            )

        # argv shape
        argv = spawn_mock.call_args[0]
        assert argv[0] == "/usr/local/bin/urh_cli"
        assert "-f" in argv
        assert argv[argv.index("-f") + 1].endswith(".complex")
        assert argv[argv.index("-s") + 1] == "2000000"
        assert argv[argv.index("-m") + 1] == "ask"
        assert argv[argv.index("-sps") + 1] == "500"

        # parsed output
        assert "bits" in result
        assert result["bit_count"] > 0
        assert result["params"]["modulation"] == "ASK"
        assert result["params"]["samples_per_symbol"] == 500

    async def test_with_optional_params(self, tmp_path: Path) -> None:
        """Threshold, invert, and bit_order surface as CLI flags."""
        iq_path = tmp_path / "test.iq"
        iq_path.write_bytes(_tiny_cs8_bytes())

        proc = _fake_proc(stdout=b"1010\n", stderr=b"")
        with (
            patch("shutil.which", return_value="/usr/local/bin/urh_cli"),
            patch("asyncio.create_subprocess_exec", return_value=proc) as spawn_mock,
        ):
            await demodulate(
                iq_path, 2_000_000, "FSK",
                samples_per_symbol=200,
                threshold=0.5,
                invert=True,
                bit_order="lsb",
            )

        argv = spawn_mock.call_args[0]
        assert "-thresh" in argv
        assert argv[argv.index("-thresh") + 1] == "0.5"
        assert "-invert" in argv
        assert "-bo" in argv
        assert argv[argv.index("-bo") + 1] == "lsb"

    async def test_temp_file_cleaned_up_on_success(self, tmp_path: Path) -> None:
        """The .complex temp file is deleted after a successful run."""
        iq_path = tmp_path / "test.iq"
        iq_path.write_bytes(_tiny_cs8_bytes())

        proc = _fake_proc(stdout=b"1010\n", stderr=b"")
        with (
            patch("shutil.which", return_value="/usr/local/bin/urh_cli"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            result = await demodulate(iq_path, 2_000_000, "ASK", 500)

        # No .complex files left behind.
        complex_files = list(tmp_path.glob("*.complex"))
        assert len(complex_files) == 0


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


class TestDemodulateErrorPaths:
    async def test_not_installed(self) -> None:
        """shutil.which returns None → UrhNotInstalled."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(UrhNotInstalled, match="pipx install"):
                await demodulate(Path("/tmp/test.iq"), 2_000_000, "ASK", 500)

    async def test_unexpected_returncode(self, tmp_path: Path) -> None:
        """Non-zero exit → UrhFailed."""
        iq_path = tmp_path / "test.iq"
        iq_path.write_bytes(_tiny_cs8_bytes())

        proc = _fake_proc(stdout=b"", stderr=b"some error", returncode=1)
        with (
            patch("shutil.which", return_value="/usr/local/bin/urh_cli"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            with pytest.raises(UrhFailed, match="some error"):
                await demodulate(iq_path, 2_000_000, "ASK", 500)

    async def test_timeout(self, tmp_path: Path) -> None:
        """Subprocess hangs → UrhFailed after timeout."""
        iq_path = tmp_path / "test.iq"
        iq_path.write_bytes(_tiny_cs8_bytes())

        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        with (
            patch("shutil.which", return_value="/usr/local/bin/urh_cli"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            with pytest.raises(UrhFailed, match="timed out"):
                await demodulate(iq_path, 2_000_000, "ASK", 500, timeout_s=0.1)
        proc.kill.assert_called_once()

    async def test_temp_file_cleaned_up_on_error(self, tmp_path: Path) -> None:
        """The .complex temp file is deleted even after a subprocess failure."""
        iq_path = tmp_path / "test.iq"
        iq_path.write_bytes(_tiny_cs8_bytes())

        proc = _fake_proc(stdout=b"", stderr=b"error", returncode=1)
        with (
            patch("shutil.which", return_value="/usr/local/bin/urh_cli"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            try:
                await demodulate(iq_path, 2_000_000, "ASK", 500)
            except UrhFailed:
                pass

        complex_files = list(tmp_path.glob("*.complex"))
        assert len(complex_files) == 0
