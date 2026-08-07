"""Unit tests for hackrf_agent.domain.capture_budget."""

from __future__ import annotations

import pytest

from hackrf_agent.domain.capture_budget import CaptureBudget


class TestFromEnv:
    def test_unset_disables_budget(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MAX_CAPTURE_MINUTES", raising=False)
        b = CaptureBudget.from_env()
        assert b.max_seconds is None
        assert b.remaining_seconds() == float("inf")

    def test_empty_string_disables_budget(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAX_CAPTURE_MINUTES", "")
        b = CaptureBudget.from_env()
        assert b.max_seconds is None

    def test_positive_number_enables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAX_CAPTURE_MINUTES", "5")
        b = CaptureBudget.from_env()
        assert b.max_seconds == 300.0

    def test_zero_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MAX_CAPTURE_MINUTES", "0")
        b = CaptureBudget.from_env()
        assert b.max_seconds is None

    def test_negative_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MAX_CAPTURE_MINUTES", "-5")
        b = CaptureBudget.from_env()
        assert b.max_seconds is None

    def test_non_numeric_disables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAX_CAPTURE_MINUTES", "not-a-number")
        b = CaptureBudget.from_env()
        assert b.max_seconds is None

    def test_fractional_minutes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAX_CAPTURE_MINUTES", "0.5")
        b = CaptureBudget.from_env()
        assert b.max_seconds == 30.0


class TestWouldExceed:
    def test_disabled_budget_always_ok(self) -> None:
        b = CaptureBudget(max_seconds=None)
        assert b.would_exceed(1e12) is False

    def test_under_cap(self) -> None:
        b = CaptureBudget(max_seconds=60.0)
        assert b.would_exceed(30.0) is False

    def test_at_cap_is_ok(self) -> None:
        # accumulated 30 + requested 30 == cap 60. Not strictly over.
        b = CaptureBudget(max_seconds=60.0, accumulated_seconds=30.0)
        assert b.would_exceed(30.0) is False

    def test_over_cap(self) -> None:
        b = CaptureBudget(max_seconds=60.0, accumulated_seconds=30.0)
        assert b.would_exceed(31.0) is True


class TestChargeAndRemaining:
    def test_charge_accumulates(self) -> None:
        b = CaptureBudget(max_seconds=60.0)
        b.charge(15.0)
        b.charge(10.0)
        assert b.accumulated_seconds == 25.0
        assert b.remaining_seconds() == 35.0

    def test_negative_charge_ignored(self) -> None:
        b = CaptureBudget(max_seconds=60.0)
        b.charge(-5.0)
        assert b.accumulated_seconds == 0.0

    def test_remaining_clamped_to_zero(self) -> None:
        b = CaptureBudget(max_seconds=10.0, accumulated_seconds=15.0)
        assert b.remaining_seconds() == 0.0
