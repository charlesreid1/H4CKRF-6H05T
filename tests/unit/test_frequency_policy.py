"""Unit tests for frequency_policy lookup functions.

Covers is_blocked, is_in_ism, is_in_amateur, range_is_blocked, and
structural band invariants.
"""

import pytest

from hackrf_agent.domain.frequency_policy import (
    AMATEUR_BANDS,
    BLOCKED_BANDS,
    ISM_BANDS,
    is_blocked,
    is_in_amateur,
    is_in_ism,
    range_is_blocked,
)

# ======================================================================
# is_blocked — blocked frequencies
# ======================================================================


class TestIsBlocked:
    @pytest.mark.parametrize(
        "freq_hz, expected_substring",
        [
            (1_090_000_000, "ADS-B"),
            (1_087_000_000, "ADS-B"),
            (1_093_000_000, "ADS-B"),
            (127_500_000, "Aviation"),
            (118_000_000, "Aviation"),
            (137_000_000, "Aviation"),
            (1_575_420_000, "GPS L1"),
            (1_227_600_000, "GPS L2"),
            (156_800_000, "Maritime"),
            (751_000_000, "Cellular"),
            (1_420_000_000, "Radio astronomy 21 cm"),
            (1_930_000_000, "Cellular"),
            (2_695_000_000, "Radio astronomy"),
        ],
    )
    def test_blocked(self, freq_hz: int, expected_substring: str) -> None:
        blocked, reason = is_blocked(freq_hz)
        assert blocked is True
        assert reason is not None
        assert expected_substring in reason

    @pytest.mark.parametrize(
        "freq_hz",
        [
            1_086_999_999,  # just below ADS-B
            1_093_000_001,  # just above ADS-B
            433_920_000,  # ISM
            915_000_000,  # ISM
            2_440_000_000,  # ISM
            100_000_000,  # unremarkable
        ],
    )
    def test_not_blocked(self, freq_hz: int) -> None:
        blocked, reason = is_blocked(freq_hz)
        assert blocked is False
        assert reason is None


# ======================================================================
# is_in_ism
# ======================================================================


class TestIsInIsm:
    @pytest.mark.parametrize(
        "freq_hz, expected_substring",
        [
            (315_000_000, "315 MHz"),
            (433_920_000, "433.05"),
            (915_000_000, "902–928"),
            (2_440_000_000, "2400"),
            (5_800_000_000, "5725"),
            (433_050_000, "433.05"),  # lower edge
            (434_790_000, "433.05"),  # upper edge
        ],
    )
    def test_in_ism(self, freq_hz: int, expected_substring: str) -> None:
        in_ism, label = is_in_ism(freq_hz)
        assert in_ism is True
        assert label is not None
        assert expected_substring in label

    @pytest.mark.parametrize(
        "freq_hz",
        [
            433_049_999,  # just below 433 ISM
            434_790_001,  # just above 433 ISM
            100_000_000,  # unremarkable
        ],
    )
    def test_not_in_ism(self, freq_hz: int) -> None:
        in_ism, label = is_in_ism(freq_hz)
        assert in_ism is False
        assert label is None


# ======================================================================
# is_in_amateur
# ======================================================================


class TestIsInAmateur:
    @pytest.mark.parametrize(
        "freq_hz, expected_substring",
        [
            (445_000_000, "70 cm"),
            (1_245_000_000, "23 cm"),
        ],
    )
    def test_in_amateur(self, freq_hz: int, expected_substring: str) -> None:
        in_amateur, label = is_in_amateur(freq_hz)
        assert in_amateur is True
        assert label is not None
        assert expected_substring in label


# ======================================================================
# range_is_blocked
# ======================================================================


class TestRangeIsBlocked:
    @pytest.mark.parametrize(
        "start_hz, stop_hz, should_block",
        [
            (1_080_000_000, 1_100_000_000, True),  # spans ADS-B
            (433_000_000, 434_000_000, False),  # inside ISM
            (1_085_000_000, 1_086_000_000, False),  # just below ADS-B
        ],
    )
    def test_range_is_blocked(
        self,
        start_hz: int,
        stop_hz: int,
        should_block: bool,
    ) -> None:
        blocked, reason = range_is_blocked(start_hz, stop_hz)
        assert blocked is should_block
        if should_block:
            assert reason is not None
        else:
            assert reason is None


# ======================================================================
# Structural band invariants
# ======================================================================


class TestBandInvariants:
    def test_blocked_bands_start_before_stop(self) -> None:
        for start_hz, stop_hz, _reason in BLOCKED_BANDS:
            assert start_hz < stop_hz, f"{start_hz} >= {stop_hz}"

    def test_ism_bands_start_before_stop(self) -> None:
        for start_hz, stop_hz, _label in ISM_BANDS:
            assert start_hz < stop_hz, f"{start_hz} >= {stop_hz}"

    def test_amateur_bands_start_before_stop(self) -> None:
        for start_hz, stop_hz, _label in AMATEUR_BANDS:
            assert start_hz < stop_hz, f"{start_hz} >= {stop_hz}"
