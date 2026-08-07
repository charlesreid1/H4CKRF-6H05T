"""Unit tests for domain models.

Guards against the most common Pydantic bugs: mutable defaults,
eval-at-import time UUIDs, and validation edge-cases.
"""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from hackrf_agent.domain.models import (
    CommandAction,
    ExecuteCommand,
    Grant,
    RiskAssessment,
    RiskLevel,
    _utcnow,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_command(action: CommandAction, **kwargs) -> ExecuteCommand:
    defaults = {
        "action": action,
        "justification": "test",
        "expected_effect": "test",
    }
    defaults.update(kwargs)
    return ExecuteCommand(**defaults)


# ---------------------------------------------------------------------------
# ExecuteCommand
# ---------------------------------------------------------------------------


class TestExecuteCommand:
    def test_valid_construction(self) -> None:
        cmd = make_command(CommandAction.GET_DEVICE_INFO)
        assert cmd.action == CommandAction.GET_DEVICE_INFO
        assert cmd.args == {}
        assert cmd.justification == "test"

    def test_empty_justification_raises(self) -> None:
        with pytest.raises(ValidationError, match="justification"):
            ExecuteCommand(
                action=CommandAction.GET_DEVICE_INFO,
                justification="",
                expected_effect="valid",
            )

    def test_whitespace_justification_raises(self) -> None:
        with pytest.raises(ValidationError, match="justification"):
            ExecuteCommand(
                action=CommandAction.GET_DEVICE_INFO,
                justification="   ",
                expected_effect="valid",
            )

    def test_empty_expected_effect_raises(self) -> None:
        with pytest.raises(ValidationError, match="expected_effect"):
            ExecuteCommand(
                action=CommandAction.GET_DEVICE_INFO,
                justification="valid",
                expected_effect="",
            )

    def test_args_default_factory_distinct(self) -> None:
        """Two instances get DISTINCT dict objects — not the same mutable default."""
        a = make_command(CommandAction.GET_DEVICE_INFO)
        b = make_command(CommandAction.GET_DEVICE_INFO)
        # Default dicts should be independent
        assert a.args is not b.args
        # Modifying one should not affect the other
        a.args["extra"] = 42
        assert "extra" not in b.args


# ---------------------------------------------------------------------------
# Grant
# ---------------------------------------------------------------------------


class TestGrant:
    def test_distinct_ids(self) -> None:
        """Two Grants get distinct UUIDs — guards against = uuid4() bug."""
        g1 = Grant(
            band_start_hz=433_000_000,
            band_stop_hz=434_000_000,
            max_gain_db=30,
            expires_at=_utcnow() + timedelta(hours=1),
        )
        g2 = Grant(
            band_start_hz=433_000_000,
            band_stop_hz=434_000_000,
            max_gain_db=30,
            expires_at=_utcnow() + timedelta(hours=1),
        )
        assert g1.id != g2.id

    def test_granted_at_set_at_construction(self) -> None:
        """granted_at is populated when the Grant is constructed.

        This guards against ``= datetime.utcnow()`` (or similar) as a field
        default, which would evaluate once at import time and give every
        instance the same timestamp.  Two instances built moments apart
        should get distinct timestamps.
        """
        g1 = Grant(
            band_start_hz=433_000_000,
            band_stop_hz=434_000_000,
            max_gain_db=30,
            expires_at=_utcnow() + timedelta(hours=1),
        )
        g2 = Grant(
            band_start_hz=433_000_000,
            band_stop_hz=434_000_000,
            max_gain_db=30,
            expires_at=_utcnow() + timedelta(hours=1),
        )
        # Both should be datetime instances (populated, not None or stale)
        assert g1.granted_at != g2.granted_at

    def test_is_active_false_when_expired(self) -> None:
        grant = Grant(
            band_start_hz=433_000_000,
            band_stop_hz=434_000_000,
            max_gain_db=30,
            expires_at=_utcnow() - timedelta(seconds=1),
        )
        assert not grant.is_active

    def test_is_active_false_when_revoked(self) -> None:
        grant = Grant(
            band_start_hz=433_000_000,
            band_stop_hz=434_000_000,
            max_gain_db=30,
            expires_at=_utcnow() + timedelta(hours=1),
            revoked_at=_utcnow(),
        )
        assert not grant.is_active

    def test_covers_frequency_edges_inclusive(self) -> None:
        grant = Grant(
            band_start_hz=100,
            band_stop_hz=200,
            max_gain_db=30,
            expires_at=_utcnow() + timedelta(hours=1),
        )
        assert grant.covers_frequency(100)  # lower edge
        assert grant.covers_frequency(200)  # upper edge
        assert not grant.covers_frequency(99)  # just below
        assert not grant.covers_frequency(201)  # just above

    def test_covers_transmission(self) -> None:
        grant = Grant(
            band_start_hz=433_000_000,
            band_stop_hz=434_000_000,
            max_gain_db=30,
            expires_at=_utcnow() + timedelta(hours=1),
        )
        # In-band, gain within cap
        assert grant.covers_transmission(433_500_000, 20)
        # In-band, gain exceeds cap
        assert not grant.covers_transmission(433_500_000, 35)
        # Out-of-band
        assert not grant.covers_transmission(440_000_000, 20)


# ---------------------------------------------------------------------------
# CommandAction enum
# ---------------------------------------------------------------------------


class TestCommandAction:
    def test_expected_values(self) -> None:
        values = {m.value for m in CommandAction}
        expected = {
            # Hardware / audit tier
            "get_device_info",
            "sweep_spectrum",
            "capture_iq",
            "transmit_iq",
            "read_iq_summary",
            "decode_ook",
            "grant_list",
            "audit_query",
            # Analysis tier (Phase 3)
            "analyze_iq_modulation",
            "analyze_iq_symbols",
            "analyze_iq_spectrogram",
            "decode_manchester",
            "decode_pwm",
            "decode_ppm",
            "decode_nrz",
            "decode_pocsag",
            "decode_ads_b",
            "decode_rtty",
            "decode_ax25",
            "decode_aprs",
            # Knowledge tier (Phase 3)
            "knowledge_list_topics",
            "knowledge_read",
            "knowledge_search",
            "knowledge_lookup_band",
            "knowledge_lookup_modulation",
            "knowledge_verify_claim",
        }
        assert values == expected


# ---------------------------------------------------------------------------
# RiskLevel enum
# ---------------------------------------------------------------------------


class TestRiskLevel:
    def test_values_are_uppercase(self) -> None:
        values = {m.value for m in RiskLevel}
        assert values == {"LOW", "MEDIUM", "HIGH", "BLOCKED"}


# ---------------------------------------------------------------------------
# RiskAssessment
# ---------------------------------------------------------------------------


class TestRiskAssessment:
    @pytest.mark.parametrize(
        "level, expected_blocked, expected_proceed",
        [
            (RiskLevel.LOW, False, True),
            (RiskLevel.MEDIUM, False, True),
            (RiskLevel.HIGH, False, True),
            (RiskLevel.BLOCKED, True, False),
        ],
    )
    def test_is_blocked_and_can_proceed(
        self,
        level: RiskLevel,
        expected_blocked: bool,
        expected_proceed: bool,
    ) -> None:
        ra = RiskAssessment(level=level, reason="test")
        assert ra.is_blocked == expected_blocked
        assert ra.can_proceed == expected_proceed
