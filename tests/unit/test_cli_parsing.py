"""Unit tests for :mod:`hackrf_agent.cli.parsing`."""

from __future__ import annotations

import pytest

from hackrf_agent.cli.parsing import parse_band, parse_duration, parse_gain_db


class TestParseBand:
    """Tests for parse_band()."""

    def test_explicit_range_433M(self) -> None:  # noqa: N802
        assert parse_band("433.05-434.79M") == (433_050_000, 434_790_000)

    def test_both_sides_unit(self) -> None:
        assert parse_band("902M-928M") == (902_000_000, 928_000_000)

    def test_single_value_ism_315(self) -> None:
        assert parse_band("315M") == (310_000_000, 320_000_000)

    def test_single_value_not_in_ism(self) -> None:
        with pytest.raises(ValueError, match="not inside"):
            parse_band("999M")

    def test_mixed_units(self) -> None:
        assert parse_band("902M-928000000") == (902_000_000, 928_000_000)

    def test_start_gte_stop(self) -> None:
        with pytest.raises(ValueError, match="must be < stop"):
            parse_band("500-400M")

    def test_garbage(self) -> None:
        with pytest.raises(ValueError, match="unparseable"):
            parse_band("garbage")

    def test_gigahertz_range(self) -> None:
        assert parse_band("2.4G-2.4835G") == (2_400_000_000, 2_483_500_000)

    def test_raw_hz_range(self) -> None:
        assert parse_band("1000000-2000000") == (1_000_000, 2_000_000)

    def test_single_value_ism_902(self) -> None:
        assert parse_band("915M") == (902_000_000, 928_000_000)

    def test_zero_hz_range_raises(self) -> None:
        with pytest.raises(ValueError, match="non-integer"):
            parse_band("0-0")


class TestParseDuration:
    """Tests for parse_duration()."""

    def test_30m(self) -> None:
        assert parse_duration("30m") == 1800

    def test_2h(self) -> None:
        assert parse_duration("2h") == 7200

    def test_90s(self) -> None:
        assert parse_duration("90s") == 90

    def test_mixed_form(self) -> None:
        with pytest.raises(ValueError, match="unparseable"):
            parse_duration("1h30m")

    def test_zero(self) -> None:
        with pytest.raises(ValueError, match="must be > 0"):
            parse_duration("0m")

    def test_garbage_duration(self) -> None:
        with pytest.raises(ValueError, match="unparseable"):
            parse_duration("eleven")

    def test_whitespace_tolerance(self) -> None:
        assert parse_duration("  30m  ") == 1800


class TestParseGainDb:
    """Tests for parse_gain_db()."""

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="gain must be"):
            parse_gain_db(-1)

    def test_zero_ok(self) -> None:
        assert parse_gain_db(0) == 0

    def test_max_ok(self) -> None:
        assert parse_gain_db(62) == 62

    def test_above_max_raises(self) -> None:
        with pytest.raises(ValueError, match="gain must be"):
            parse_gain_db(63)

    def test_mid_range_ok(self) -> None:
        assert parse_gain_db(30) == 30
