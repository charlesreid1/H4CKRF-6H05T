"""Unit tests for RiskAssessor.assess() decision tree.

Covers every branch: read-only, sweep, capture, transmit with blocked
bands / ISM / amateur / grants, and defensive unknown-action handling.
"""

from datetime import timedelta

import pytest

from hackrf_agent.domain.models import (
    CommandAction,
    ExecuteCommand,
    Grant,
    RiskLevel,
    _utcnow,
)
from hackrf_agent.domain.risk_assessor import RiskAssessor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_command(action: CommandAction, **args) -> ExecuteCommand:
    return ExecuteCommand(
        action=action,
        args=dict(args),
        justification="test",
        expected_effect="test",
    )


def active_grant(
    start_hz: int,
    stop_hz: int,
    max_gain_db: int,
    *,
    expired: bool = False,
) -> Grant:
    expires_at = _utcnow() - timedelta(hours=1) if expired else _utcnow() + timedelta(hours=1)  # noqa: SIM108
    return Grant(
        band_start_hz=start_hz,
        band_stop_hz=stop_hz,
        max_gain_db=max_gain_db,
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def assessor() -> RiskAssessor:
    return RiskAssessor()


# ---------------------------------------------------------------------------
# Read-only / always-LOW actions
# ---------------------------------------------------------------------------


class TestReadOnlyActions:
    @pytest.mark.parametrize(
        "action",
        [
            CommandAction.GET_DEVICE_INFO,
            CommandAction.GRANT_LIST,
            CommandAction.AUDIT_QUERY,
            CommandAction.READ_IQ_SUMMARY,
        ],
    )
    def test_always_low(
        self,
        assessor: RiskAssessor,
        action: CommandAction,
    ) -> None:
        result = assessor.assess(make_command(action), [])
        assert result.level == RiskLevel.LOW
        assert result.requires_confirmation is False


class TestAnalysisActions:
    """Analysis-tier actions are hardcoded LOW. Cannot cause RF emission."""

    @pytest.mark.parametrize(
        "action",
        [
            CommandAction.ANALYZE_IQ_MODULATION,
            CommandAction.ANALYZE_IQ_SYMBOLS,
            CommandAction.ANALYZE_IQ_SPECTROGRAM,
            CommandAction.DECODE_MANCHESTER,
            CommandAction.DECODE_PWM,
            CommandAction.DECODE_PPM,
            CommandAction.DECODE_NRZ,
            CommandAction.DECODE_POCSAG,
            CommandAction.DECODE_ADS_B,
            CommandAction.DECODE_RTTY,
            CommandAction.DECODE_AX25,
            CommandAction.DECODE_APRS,
        ],
    )
    def test_always_low_no_approval(
        self,
        assessor: RiskAssessor,
        action: CommandAction,
    ) -> None:
        result = assessor.assess(make_command(action), [])
        assert result.level == RiskLevel.LOW
        assert result.requires_confirmation is False


class TestKnowledgeActions:
    """Knowledge-tier actions are hardcoded LOW. Cannot cause RF emission."""

    @pytest.mark.parametrize(
        "action",
        [
            CommandAction.KNOWLEDGE_LIST_TOPICS,
            CommandAction.KNOWLEDGE_READ,
            CommandAction.KNOWLEDGE_SEARCH,
            CommandAction.KNOWLEDGE_LOOKUP_BAND,
            CommandAction.KNOWLEDGE_LOOKUP_MODULATION,
            CommandAction.KNOWLEDGE_VERIFY_CLAIM,
        ],
    )
    def test_always_low_no_approval(
        self,
        assessor: RiskAssessor,
        action: CommandAction,
    ) -> None:
        result = assessor.assess(make_command(action), [])
        assert result.level == RiskLevel.LOW
        assert result.requires_confirmation is False


# ---------------------------------------------------------------------------
# sweep_spectrum
# ---------------------------------------------------------------------------


class TestSweepSpectrum:
    def test_short_sweep_low(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.SWEEP_SPECTRUM,
                start_freq_hz=433_000_000,
                end_freq_hz=434_000_000,
                dwell_s=1.0,
            ),
            [],
        )
        assert result.level == RiskLevel.LOW
        assert result.requires_confirmation is False

    def test_long_sweep_medium(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.SWEEP_SPECTRUM,
                start_freq_hz=433_000_000,
                end_freq_hz=434_000_000,
                dwell_s=5.0,
            ),
            [],
        )
        assert result.level == RiskLevel.MEDIUM
        assert result.requires_confirmation is True

    def test_dwell_omitted_defaults_to_low(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.SWEEP_SPECTRUM,
                start_freq_hz=433_000_000,
                end_freq_hz=434_000_000,
            ),
            [],
        )
        assert result.level == RiskLevel.LOW

    def test_sweep_crosses_adsb_still_low(self, assessor: RiskAssessor) -> None:
        """RX sweeps across blocked bands are NOT blocked — RX is fine."""
        result = assessor.assess(
            make_command(
                CommandAction.SWEEP_SPECTRUM,
                start_freq_hz=1_080_000_000,
                end_freq_hz=1_100_000_000,
                dwell_s=1.0,
            ),
            [],
        )
        assert result.level == RiskLevel.LOW

    def test_sweep_crosses_gps_l1_still_low(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.SWEEP_SPECTRUM,
                start_freq_hz=1_570_000_000,
                end_freq_hz=1_580_000_000,
                dwell_s=1.0,
            ),
            [],
        )
        assert result.level == RiskLevel.LOW

    def test_equal_start_and_end_blocked(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.SWEEP_SPECTRUM,
                start_freq_hz=433_000_000,
                end_freq_hz=433_000_000,
            ),
            [],
        )
        assert result.level == RiskLevel.BLOCKED
        assert "invalid sweep range" in result.reason

    def test_missing_start_blocked(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.SWEEP_SPECTRUM,
                end_freq_hz=434_000_000,
            ),
            [],
        )
        assert result.level == RiskLevel.BLOCKED
        assert "start_freq_hz" in (result.blocked_reason or "")


# ---------------------------------------------------------------------------
# capture_iq
# ---------------------------------------------------------------------------


class TestCaptureIq:
    def test_short_capture_low(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.CAPTURE_IQ,
                center_freq_hz=433_920_000,
                duration_s=2.0,
            ),
            [],
        )
        assert result.level == RiskLevel.LOW

    def test_boundary_5s_low(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.CAPTURE_IQ,
                center_freq_hz=433_920_000,
                duration_s=5.0,
            ),
            [],
        )
        assert result.level == RiskLevel.LOW

    def test_long_capture_medium(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.CAPTURE_IQ,
                center_freq_hz=433_920_000,
                duration_s=10.0,
            ),
            [],
        )
        assert result.level == RiskLevel.MEDIUM
        assert result.requires_confirmation is True

    def test_adsb_capture_rx_fine(self, assessor: RiskAssessor) -> None:
        """Capture on ADS-B frequency is fine — RX is not blocked."""
        result = assessor.assess(
            make_command(
                CommandAction.CAPTURE_IQ,
                center_freq_hz=1_090_000_000,
                duration_s=1.0,
            ),
            [],
        )
        assert result.level == RiskLevel.LOW

    def test_gps_l1_capture_rx_fine(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.CAPTURE_IQ,
                center_freq_hz=1_575_420_000,
                duration_s=1.0,
            ),
            [],
        )
        assert result.level == RiskLevel.LOW

    def test_maritime_capture_rx_fine(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.CAPTURE_IQ,
                center_freq_hz=156_800_000,
                duration_s=1.0,
            ),
            [],
        )
        assert result.level == RiskLevel.LOW

    def test_adsb_long_capture_medium(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.CAPTURE_IQ,
                center_freq_hz=1_090_000_000,
                duration_s=10.0,
            ),
            [],
        )
        assert result.level == RiskLevel.MEDIUM

    def test_negative_duration_blocked(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.CAPTURE_IQ,
                center_freq_hz=433_920_000,
                duration_s=-1.0,
            ),
            [],
        )
        assert result.level == RiskLevel.BLOCKED
        assert "invalid duration" in result.reason

    def test_missing_duration_blocked(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.CAPTURE_IQ,
                center_freq_hz=433_920_000,
            ),
            [],
        )
        assert result.level == RiskLevel.BLOCKED
        assert "duration_s" in (result.blocked_reason or "")


# ---------------------------------------------------------------------------
# transmit_iq — hardware / arg limits
# ---------------------------------------------------------------------------


class TestTransmitIqHardwareLimits:
    def test_gain_exceeds_hardware_max_blocked(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=433_920_000,
                tx_vga_gain_db=50,
            ),
            [],
        )
        assert result.level == RiskLevel.BLOCKED
        assert "47" in result.reason

    def test_negative_gain_blocked(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=433_920_000,
                tx_vga_gain_db=-1,
            ),
            [],
        )
        assert result.level == RiskLevel.BLOCKED
        assert "negative" in result.reason

    def test_missing_gain_blocked(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=433_920_000,
            ),
            [],
        )
        assert result.level == RiskLevel.BLOCKED
        assert "tx_vga_gain_db" in (result.blocked_reason or "")


# ---------------------------------------------------------------------------
# transmit_iq — blocked bands
# ---------------------------------------------------------------------------


class TestTransmitIqBlockedBands:
    @pytest.mark.parametrize(
        "freq_hz, label",
        [
            (1_090_000_000, "ADS-B"),
            (1_575_420_000, "GPS L1"),
            (121_500_000, "VHF Guard"),
            (751_000_000, "cellular"),
        ],
    )
    def test_blocked_tx(
        self,
        assessor: RiskAssessor,
        freq_hz: int,
        label: str,
    ) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=freq_hz,
                tx_vga_gain_db=10,
            ),
            [],
        )
        assert result.level == RiskLevel.BLOCKED, f"{label}: expected BLOCKED, got {result.level}"


# ---------------------------------------------------------------------------
# transmit_iq — ISM without grant
# ---------------------------------------------------------------------------


class TestTransmitIqIsmNoGrant:
    def test_ism_gain_20_medium(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=433_920_000,
                tx_vga_gain_db=20,
            ),
            [],
        )
        assert result.level == RiskLevel.MEDIUM
        assert result.requires_confirmation is True

    def test_ism_gain_30_boundary_medium(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=433_920_000,
                tx_vga_gain_db=30,
            ),
            [],
        )
        assert result.level == RiskLevel.MEDIUM

    def test_ism_gain_35_high(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=433_920_000,
                tx_vga_gain_db=35,
            ),
            [],
        )
        assert result.level == RiskLevel.HIGH
        assert result.requires_confirmation is True

    def test_ism_gain_47_high(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=433_920_000,
                tx_vga_gain_db=47,
            ),
            [],
        )
        assert result.level == RiskLevel.HIGH

    def test_ism_edge_902_medium(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=902_000_000,
                tx_vga_gain_db=20,
            ),
            [],
        )
        assert result.level == RiskLevel.MEDIUM


# ---------------------------------------------------------------------------
# transmit_iq — with grants
# ---------------------------------------------------------------------------


class TestTransmitIqWithGrants:
    def test_grant_fully_covers_low(self, assessor: RiskAssessor) -> None:
        """In-scope grant → LOW, no confirmation prompt (pre-authorized)."""
        grant = active_grant(433_000_000, 434_000_000, max_gain_db=30)
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=433_920_000,
                tx_vga_gain_db=20,
            ),
            [grant],
        )
        assert result.level == RiskLevel.LOW
        assert result.requires_confirmation is False
        assert "in-scope grant" in result.reason

    def test_grant_gain_exceeded_falls_to_ism_high(self, assessor: RiskAssessor) -> None:
        grant = active_grant(433_000_000, 434_000_000, max_gain_db=30)
        # Gain 35 exceeds grant cap → falls through to ISM rule → gain > 30 → HIGH
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=433_920_000,
                tx_vga_gain_db=35,
            ),
            [grant],
        )
        assert result.level == RiskLevel.HIGH

    def test_grant_out_of_band_unclassified_high(self, assessor: RiskAssessor) -> None:
        grant = active_grant(433_000_000, 434_000_000, max_gain_db=30)
        # 470 MHz is outside the grant and not in ISM or amateur
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=470_000_000,
                tx_vga_gain_db=20,
            ),
            [grant],
        )
        assert result.level == RiskLevel.HIGH

    def test_expired_grant_ism_medium(self, assessor: RiskAssessor) -> None:
        """Expired grant → ISM rule applies; 433.5 MHz with gain 20 ≤ 30 → MEDIUM."""
        expired = active_grant(433_000_000, 434_000_000, max_gain_db=30, expired=True)
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=433_500_000,
                tx_vga_gain_db=20,
            ),
            [expired],
        )
        assert result.level == RiskLevel.MEDIUM


# ---------------------------------------------------------------------------
# transmit_iq — amateur bands
# ---------------------------------------------------------------------------


class TestTransmitIqAmateur:
    def test_70cm_high(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=445_000_000,
                tx_vga_gain_db=20,
            ),
            [],
        )
        assert result.level == RiskLevel.HIGH
        assert "amateur" in result.reason

    def test_23cm_high(self, assessor: RiskAssessor) -> None:
        # 1255 MHz is in 23cm amateur (1240–1300) but between GLONASS G2
        # (up to 1254.4275) and Galileo E6 (from 1260), so it is NOT blocked.
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=1_255_000_000,
                tx_vga_gain_db=20,
            ),
            [],
        )
        assert result.level == RiskLevel.HIGH
        assert "amateur" in result.reason

    def test_ism_wins_over_amateur_33cm(self, assessor: RiskAssessor) -> None:
        """915 MHz is in both ISM 902 and 33 cm amateur — ISM wins."""
        result = assessor.assess(
            make_command(
                CommandAction.TRANSMIT_IQ,
                center_freq_hz=915_000_000,
                tx_vga_gain_db=20,
            ),
            [],
        )
        assert result.level == RiskLevel.MEDIUM


# ---------------------------------------------------------------------------
# Unknown action (defensive)
# ---------------------------------------------------------------------------


class TestUnknownAction:
    @pytest.mark.skip(
        reason="Python str,Enum rejects unknown values; defensive branch is unreachable"
    )
    def test_monkey_patched_enum_blocked(self, assessor: RiskAssessor) -> None:
        """A CommandAction not in the decision tree → BLOCKED.

        Skipped: Python's ``str, Enum`` rejects unknown values at construction
        time, so the defensive ``BLOCKED("unknown action")`` branch in
        ``RiskAssessor.assess()`` is unreachable via normal Pydantic flows.
        We keep the branch in the code as defense-in-depth against future
        enum changes or custom validation.
        """


# ---------------------------------------------------------------------------
# sweep_spectrum_bulk aggregate cost
# ---------------------------------------------------------------------------


class TestSweepSpectrumBulkAggregate:
    """The per-range dwell is only one input to risk. n_ranges * dwell_s
    (aggregate wall-clock) also matters — a hostile fan-out of 100 short
    sweeps is still 100 s of RX and 100 s of holding the driver lock.
    """

    def _ranges(self, count: int) -> list[dict[str, int]]:
        # Non-overlapping 1 MHz windows starting at 100 MHz.
        return [
            {"start_freq_hz": 100_000_000 + i * 2_000_000,
             "end_freq_hz": 100_500_000 + i * 2_000_000}
            for i in range(count)
        ]

    def test_15_ranges_x_1s_dwell_stays_low(self, assessor: RiskAssessor) -> None:
        # 15 * 1 s = 15 s aggregate, ≤ 30 s cap → LOW.
        result = assessor.assess(
            make_command(
                CommandAction.SWEEP_SPECTRUM_BULK,
                ranges=self._ranges(15),
                dwell_s=1.0,
            ),
            [],
        )
        assert result.level == RiskLevel.LOW

    def test_16_ranges_x_2s_dwell_medium_by_aggregate(
        self, assessor: RiskAssessor
    ) -> None:
        # per-range dwell = 2 s is at the LOW boundary, but 16 * 2 = 32 s
        # aggregate exceeds the 30 s LOW cap → MEDIUM.
        result = assessor.assess(
            make_command(
                CommandAction.SWEEP_SPECTRUM_BULK,
                ranges=self._ranges(16),
                dwell_s=2.0,
            ),
            [],
        )
        assert result.level == RiskLevel.MEDIUM
        assert result.requires_confirmation is True
        assert "aggregate" in result.reason.lower()

    def test_2_ranges_x_1s_low(self, assessor: RiskAssessor) -> None:
        result = assessor.assess(
            make_command(
                CommandAction.SWEEP_SPECTRUM_BULK,
                ranges=self._ranges(2),
                dwell_s=1.0,
            ),
            [],
        )
        assert result.level == RiskLevel.LOW

    def test_long_per_range_dwell_medium(self, assessor: RiskAssessor) -> None:
        # dwell > 2 s → MEDIUM regardless of aggregate.
        result = assessor.assess(
            make_command(
                CommandAction.SWEEP_SPECTRUM_BULK,
                ranges=self._ranges(2),
                dwell_s=5.0,
            ),
            [],
        )
        assert result.level == RiskLevel.MEDIUM
