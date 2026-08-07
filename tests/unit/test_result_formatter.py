"""Tests for result_formatter.py — per-action format_* methods.

Every output must be JSON-serializable with no custom encoder.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hackrf_agent.domain.models import DeviceInfo
from hackrf_agent.domain.result_formatter import ResultFormatter
from hackrf_agent.domain.session import new_session


@pytest.fixture
def fmt() -> ResultFormatter:
    return ResultFormatter()


@pytest.fixture
def paths(tmp_path: Path):
    return new_session(tmp_path)


@pytest.fixture
def synth_iq_bytes() -> bytes:
    """A synthetic int8 IQ blob big enough for an FFT (2^13 samples)."""
    t = np.arange(8192, dtype=np.float32) / 2_000_000.0
    complex_iq = np.exp(2j * np.pi * 100_000.0 * t).astype(np.complex64)
    i = (complex_iq.real * 100).astype(np.int8)
    q = (complex_iq.imag * 100).astype(np.int8)
    interleaved = np.empty(i.size * 2, dtype=np.int8)
    interleaved[0::2] = i
    interleaved[1::2] = q
    return interleaved.tobytes()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _assert_json_serializable(obj: object) -> None:
    """Assert that obj can be round-tripped through json.dumps."""
    try:
        json.dumps(obj)
    except TypeError as e:
        pytest.fail(f"Value not JSON-serializable: {obj!r} — {e}")


# ---------------------------------------------------------------------------
# format_device_info
# ---------------------------------------------------------------------------


class TestFormatDeviceInfo:
    def test_returns_expected_keys(self, fmt: ResultFormatter) -> None:
        info = DeviceInfo(serial="s1", firmware_version="fw", board_revision="r1", part_id="p1")
        result = fmt.format_device_info(info)
        assert result == {
            "serial": "s1",
            "firmware_version": "fw",
            "board_revision": "r1",
            "part_id": "p1",
        }
        _assert_json_serializable(result)


# ---------------------------------------------------------------------------
# format_sweep
# ---------------------------------------------------------------------------


class TestFormatSweep:
    def test_returns_expected_keys(self, fmt: ResultFormatter) -> None:
        """format_sweep returns expected keys with JSON-primitive values."""
        n = 4096
        mag = np.zeros(n, dtype=np.float32)
        freqs = np.arange(n, dtype=np.float64)
        result = fmt.format_sweep(
            magnitude_db=mag, freqs_hz=freqs, start_hz=100_000_000, stop_hz=200_000_000
        )
        assert set(result.keys()) == {
            "start_hz",
            "stop_hz",
            "num_bins",
            "noise_floor_dbfs",
            "peaks",
            "truncated",
        }
        assert result["num_bins"] == n
        assert isinstance(result["noise_floor_dbfs"], float)
        assert isinstance(result["peaks"], list)
        assert result["truncated"] is False
        _assert_json_serializable(result)

    def test_truncated_flag_surfaces(self, fmt: ResultFormatter) -> None:
        """truncated=True when the caller passes it through."""
        n = 4096
        mag = np.zeros(n, dtype=np.float32)
        freqs = np.arange(n, dtype=np.float64)
        result = fmt.format_sweep(
            magnitude_db=mag,
            freqs_hz=freqs,
            start_hz=100_000_000,
            stop_hz=200_000_000,
            truncated=True,
        )
        assert result["truncated"] is True

    def test_strong_tone_in_peaks(self, fmt: ResultFormatter) -> None:
        """A strong tone in the spectrum appears in peaks[0]."""
        n = 4096
        # Put a strong tone at bin 1024.
        mag = np.full(n, -90.0, dtype=np.float32)
        mag[1024] = -10.0
        freqs = np.arange(n, dtype=np.float64) * 1e6 / n + 100_000_000.0
        result = fmt.format_sweep(
            magnitude_db=mag, freqs_hz=freqs, start_hz=100_000_000, stop_hz=200_000_000
        )
        assert len(result["peaks"]) > 0
        assert result["peaks"][0]["power_dbfs"] == pytest.approx(-10.0)


# ---------------------------------------------------------------------------
# format_capture
# ---------------------------------------------------------------------------


class TestFormatCapture:
    def test_returns_expected_shape(
        self, fmt: ResultFormatter, paths, synth_iq_bytes: bytes
    ) -> None:
        """format_capture writes IQ, returns dict with summary."""
        iq_path = paths.new_iq_path("capture")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(synth_iq_bytes)

        result = fmt.format_capture(
            iq_path=iq_path,
            center_hz=433_000_000,
            sample_rate_hz=2_000_000,
            num_samples=len(synth_iq_bytes) // 2,
            session_paths=paths,
        )
        assert result["iq_path"] == str(iq_path)
        assert result["num_samples"] == len(synth_iq_bytes) // 2
        assert len(result["peaks"]) > 0  # 100 kHz tone should be detected
        _assert_json_serializable(result)

    def test_path_outside_root_raises(self, fmt: ResultFormatter, paths) -> None:
        """format_capture with iq_path outside session root raises ValueError."""
        with pytest.raises(ValueError, match="escapes session root"):
            fmt.format_capture(
                iq_path=Path("/tmp/x.iq"),
                center_hz=433_000_000,
                sample_rate_hz=2_000_000,
                num_samples=1024,
                session_paths=paths,
            )

    def test_tiny_capture_returns_skeleton(self, fmt: ResultFormatter, paths) -> None:
        """A capture shorter than 64 samples returns the skeleton dict."""
        tiny = b"\x00\x01" * 10  # 20 bytes = 10 samples
        iq_path = paths.new_iq_path("tiny")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(tiny)

        result = fmt.format_capture(
            iq_path=iq_path,
            center_hz=100_000_000,
            sample_rate_hz=2_000_000,
            num_samples=10,
            session_paths=paths,
        )
        assert result["note"] == "capture too short for spectral summary"
        assert result["noise_floor_dbfs"] is None
        assert result["peaks"] == []


# ---------------------------------------------------------------------------
# format_transmit
# ---------------------------------------------------------------------------


class TestFormatTransmit:
    def test_returns_expected_shape(self, fmt: ResultFormatter) -> None:
        result = fmt.format_transmit(
            center_hz=433_000_000,
            sample_rate_hz=2_000_000,
            iq_path=Path("/tmp/tx.iq"),
            txvga_gain_db=30,
            duration_s=1.5,
        )
        assert set(result.keys()) == {
            "center_hz",
            "sample_rate_hz",
            "iq_path",
            "txvga_gain_db",
            "duration_s",
        }
        assert result["duration_s"] == 1.5
        assert isinstance(result["iq_path"], str)
        _assert_json_serializable(result)


# ---------------------------------------------------------------------------
# All outputs JSON-serializable
# ---------------------------------------------------------------------------


class TestAllFormatsJson:
    def test_device_info_json(self, fmt: ResultFormatter) -> None:
        info = DeviceInfo("s", "fw", "r", "p")
        _assert_json_serializable(fmt.format_device_info(info))

    def test_sweep_json(self, fmt: ResultFormatter) -> None:
        _assert_json_serializable(
            fmt.format_sweep(
                magnitude_db=np.zeros(256, dtype=np.float32),
                freqs_hz=np.arange(256, dtype=np.float64),
                start_hz=100_000_000,
                stop_hz=200_000_000,
            )
        )

    def test_grant_list_empty_json(self, fmt: ResultFormatter) -> None:
        result = fmt.format_grant_list([])
        assert result == {"count": 0, "grants": []}
        _assert_json_serializable(result)

    def test_audit_query_empty_json(self, fmt: ResultFormatter) -> None:
        result = fmt.format_audit_query([])
        assert result == {"count": 0, "rows": []}
        _assert_json_serializable(result)
