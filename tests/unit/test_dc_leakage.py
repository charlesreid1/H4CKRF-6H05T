"""Unit tests for DC/LO leakage handling (Task 2)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.args import CaptureIqArgs
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.handlers import HANDLERS, HandlerContext
from hackrf_agent.domain.models import CommandAction
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.result_formatter import _annotate_artifacts, _hop_centers
from hackrf_agent.domain.session import new_session
from tests.support.fake_driver import FakeDriver


@pytest.fixture
async def ctx(tmp_path: Path):
    db = tmp_path / "agent.db"
    await ensure_schema(db)
    perms = PermissionService(db)
    driver = FakeDriver()
    async with AuditService(db) as audit:
        yield HandlerContext(
            driver=driver,
            permissions=perms,
            audit=audit,
            session_paths=new_session(tmp_path / "sessions"),
        )


# ---------------------------------------------------------------------------
# 2a — Capture I/Q offset tuning
# ---------------------------------------------------------------------------


class TestCaptureIqOffsetTuning:
    """CaptureIqArgs with target_freq_hz computes an offset center."""

    async def test_target_freq_hz_picks_offset_center(self, ctx: HandlerContext) -> None:
        """target_freq_hz=433_920_000, SR=8 MHz → center = 433.92 + 2 MHz."""
        result = await HANDLERS[CommandAction.CAPTURE_IQ](
            ctx,
            {
                "target_freq_hz": 433_920_000,
                "sample_rate_hz": 8_000_000,
                "duration_s": 0.1,
            },
        )
        assert result["kind"] == "capture"
        # Driver was called.
        assert len(ctx.driver.calls) >= 1
        _name, call_kwargs = ctx.driver.calls[0]
        expected_center = 433_920_000 + 8_000_000 // 4  # = 435_920_000
        assert call_kwargs["center_hz"] == expected_center
        assert result["center_hz"] == expected_center
        assert result["target_hz"] == 433_920_000

    async def test_center_freq_hz_passthrough(self, ctx: HandlerContext) -> None:
        """center_freq_hz is passed through to the driver unchanged."""
        result = await HANDLERS[CommandAction.CAPTURE_IQ](
            ctx,
            {
                "center_freq_hz": 433_920_000,
                "sample_rate_hz": 2_000_000,
                "duration_s": 0.1,
            },
        )
        assert result["kind"] == "capture"
        _name, call_kwargs = ctx.driver.calls[0]
        assert call_kwargs["center_hz"] == 433_920_000
        assert result["center_hz"] == 433_920_000
        assert result["target_hz"] is None


# ---------------------------------------------------------------------------
# 2a — Validation (mutual exclusivity)
# ---------------------------------------------------------------------------


class TestCaptureIqValidation:
    """CaptureIqArgs requires exactly one of center_freq_hz or target_freq_hz."""

    def test_both_fields_fails(self) -> None:
        with pytest.raises(ValidationError):
            CaptureIqArgs(
                center_freq_hz=433_000_000,
                target_freq_hz=433_000_000,
                duration_s=1.0,
            )

    def test_neither_field_fails(self) -> None:
        with pytest.raises(ValidationError):
            CaptureIqArgs(duration_s=1.0)

    def test_center_freq_hz_negative_fails(self) -> None:
        with pytest.raises(ValidationError):
            CaptureIqArgs(center_freq_hz=-1, duration_s=1.0)


# ---------------------------------------------------------------------------
# 2b — DC-spike peak flagging
# ---------------------------------------------------------------------------


class TestHopCenters:
    """_hop_centers computes tuner center frequencies for sweep steps."""

    def test_basic(self) -> None:
        centers = _hop_centers(
            start_hz=433_000_000, stop_hz=435_000_000, sample_rate_hz=2_000_000
        )
        # With SR=2 MHz and range 433-435 MHz (2 MHz wide):
        # centers = [433 + 1 = 434_000_000]
        assert len(centers) >= 1
        assert centers[0] == pytest.approx(434_000_000)

    def test_wider_band(self) -> None:
        centers = _hop_centers(
            start_hz=100_000_000, stop_hz=110_000_000, sample_rate_hz=5_000_000
        )
        # SR=5 MHz, band 100-110 → 10 MHz wide → ~2 hops
        # centers at 102.5 MHz, 107.5 MHz
        assert len(centers) >= 2
        assert centers[0] == pytest.approx(102_500_000)
        assert centers[1] == pytest.approx(107_500_000)


class TestAnnotateArtifacts:
    """_annotate_artifacts flags peaks that land on hop centers."""

    def test_peak_on_hop_center_flagged(self) -> None:
        peaks = [{"freq_hz": 434_000_000, "power_db": -30}]
        annotated = _annotate_artifacts(
            peaks,
            start_hz=433_000_000,
            stop_hz=435_000_000,
            sample_rate_hz=2_000_000,
            fft_size=4096,
        )
        assert annotated[0]["is_artifact"] is True
        assert annotated[0]["artifact_reason"] is not None
        assert "DC/LO" in annotated[0]["artifact_reason"]

    def test_peak_away_from_hop_center_not_flagged(self) -> None:
        # 433_920_000 is 80 kHz from hop center 434_000_000.
        # With SR=2 MHz, FFT=4096: bin_width ≈ 488 Hz, tolerance = max(976, 5000) = 5000.
        # 80_000 > 5_000 → not flagged.
        peaks = [{"freq_hz": 433_920_000, "power_db": -30}]
        annotated = _annotate_artifacts(
            peaks,
            start_hz=433_000_000,
            stop_hz=435_000_000,
            sample_rate_hz=2_000_000,
            fft_size=4096,
        )
        assert annotated[0]["is_artifact"] is False
        assert annotated[0]["artifact_reason"] is None

    def test_tolerance_uses_5khz_floor(self) -> None:
        """tolerance_hz is max(2*bin_width, 5000). Verify 5 kHz floor applies."""
        peaks = [{"freq_hz": 434_003_000, "power_db": -30}]
        # With SR=2M, FFT=4096: bin_width ≈ 488 Hz, tolerance = 5000.
        # 434_003_000 is 3 kHz from hop center 434_000_000 → flagged.
        annotated = _annotate_artifacts(
            peaks,
            start_hz=433_000_000,
            stop_hz=435_000_000,
            sample_rate_hz=2_000_000,
            fft_size=4096,
        )
        assert annotated[0]["is_artifact"] is True
