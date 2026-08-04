"""Unit tests for ``PermissionService`` — Grant CRUD with TTL-aware reads."""

from datetime import UTC, datetime

import pytest

import hackrf_agent.domain.permission_service as ps_mod
from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.permission_service import PermissionService

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def permissions(tmp_path):
    """A PermissionService pointed at a temp file with schema applied."""
    db = tmp_path / "agent.db"
    await ensure_schema(db)
    return PermissionService(db)


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------


class TestGrantBasic:
    async def test_grant_returns_populated_grant(self, permissions):
        g = await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        assert g.band_start_hz == 433_050_000
        assert g.band_stop_hz == 434_790_000
        assert g.kind == "tx"
        assert g.max_gain_db == 30
        assert g.revoked_at is None

    async def test_get_roundtrip(self, permissions):
        g = await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        retrieved = await permissions.get(g.id)
        assert retrieved is not None
        assert retrieved.id == g.id
        assert retrieved.band_start_hz == g.band_start_hz

    async def test_list_active_includes_fresh_grant(self, permissions):
        g = await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        active = await permissions.list_active()
        assert len(active) == 1
        assert active[0].id == g.id

    async def test_two_grants_distinct_ids(self, permissions):
        g1 = await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        g2 = await permissions.grant(
            band_start_hz=902_000_000,
            band_stop_hz=928_000_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        assert g1.id != g2.id


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestGrantValidation:
    async def test_equal_start_and_stop_raises(self, permissions):
        with pytest.raises(ValueError, match="band_start_hz must be <"):
            await permissions.grant(
                band_start_hz=433_000_000,
                band_stop_hz=433_000_000,
                max_gain_db=30,
                ttl_seconds=1800,
            )

    async def test_negative_max_gain_raises(self, permissions):
        with pytest.raises(ValueError, match="max_gain_db must be >= 0"):
            await permissions.grant(
                band_start_hz=433_050_000,
                band_stop_hz=434_790_000,
                max_gain_db=-1,
                ttl_seconds=1800,
            )

    async def test_zero_ttl_raises(self, permissions):
        with pytest.raises(ValueError, match="ttl_seconds must be > 0"):
            await permissions.grant(
                band_start_hz=433_050_000,
                band_stop_hz=434_790_000,
                max_gain_db=30,
                ttl_seconds=0,
            )


# ---------------------------------------------------------------------------
# TTL / expiry
# ---------------------------------------------------------------------------


class TestExpiry:
    async def test_expired_grant_not_in_list_active(self, permissions, monkeypatch):
        """A grant whose TTL has elapsed should not appear in list_active."""
        fake_time = [datetime(2026, 1, 1, tzinfo=UTC)]
        monkeypatch.setattr(ps_mod, "_utcnow", lambda: fake_time[0])

        await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=60,
        )

        # Fast-forward 5 minutes
        fake_time[0] = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
        active = await permissions.list_active()
        assert active == []

    async def test_far_future_grant_stays_active(self, permissions):
        await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=86_400,  # 24 hours
        )
        active = await permissions.list_active()
        assert len(active) == 1


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------


class TestRevoke:
    async def test_revoke_active_grant_returns_true(self, permissions):
        g = await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        assert await permissions.revoke(g.id) is True

    async def test_second_revoke_returns_false(self, permissions):
        g = await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        assert await permissions.revoke(g.id) is True
        assert await permissions.revoke(g.id) is False

    async def test_revoked_not_in_list_active(self, permissions):
        g = await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        await permissions.revoke(g.id)
        active = await permissions.list_active()
        assert len(active) == 0


# ---------------------------------------------------------------------------
# revoke_all_tx
# ---------------------------------------------------------------------------


class TestRevokeAllTx:
    async def test_revokes_active_transmit_grants(self, permissions):
        await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        await permissions.grant(
            band_start_hz=902_000_000,
            band_stop_hz=928_000_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        await permissions.grant(
            band_start_hz=2_400_000_000,
            band_stop_hz=2_483_500_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )

        count = await permissions.revoke_all_tx()
        assert count == 3

        active = await permissions.list_active()
        assert active == []

    async def test_idempotent_second_call_returns_zero(self, permissions):
        await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        assert await permissions.revoke_all_tx() == 1
        assert await permissions.revoke_all_tx() == 0

    async def test_already_revoked_not_double_counted(self, permissions):
        g = await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        await permissions.revoke(g.id)
        # revoke_all_tx should NOT count the already-revoked grant.
        assert await permissions.revoke_all_tx() == 0


# ---------------------------------------------------------------------------
# list_all
# ---------------------------------------------------------------------------


class TestListAll:
    async def test_includes_expired_and_revoked(self, permissions, monkeypatch):
        fake_time = [datetime(2026, 1, 1, tzinfo=UTC)]
        monkeypatch.setattr(ps_mod, "_utcnow", lambda: fake_time[0])

        g1 = await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=60,
        )
        # Fast-forward to expire
        fake_time[0] = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
        g2 = await permissions.grant(
            band_start_hz=902_000_000,
            band_stop_hz=928_000_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        await permissions.revoke(g2.id)

        all_grants = await permissions.list_all()
        ids = {g.id for g in all_grants}
        assert g1.id in ids  # expired
        assert g2.id in ids  # revoked

    async def test_ordered_newest_first(self, permissions):
        g1 = await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        g2 = await permissions.grant(
            band_start_hz=902_000_000,
            band_stop_hz=928_000_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        all_grants = await permissions.list_all()
        # Newest first → g2 (created second) before g1.
        assert all_grants[0].id == g2.id
        assert all_grants[1].id == g1.id


# ---------------------------------------------------------------------------
# Timestamp round-trip
# ---------------------------------------------------------------------------


class TestTimestampRoundTrip:
    async def test_timestamps_are_utc_aware(self, permissions):
        g = await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        retrieved = await permissions.get(g.id)
        assert retrieved is not None
        assert retrieved.granted_at.tzinfo is not None
        assert retrieved.granted_at.tzinfo is UTC
        assert retrieved.expires_at.tzinfo is not None
        assert retrieved.expires_at.tzinfo is UTC


# ---------------------------------------------------------------------------
# Filter by kind
# ---------------------------------------------------------------------------


class TestFilterByKind:
    async def test_list_active_kind_filter(self, permissions):
        await permissions.grant(
            band_start_hz=433_050_000,
            band_stop_hz=434_790_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        await permissions.grant(
            band_start_hz=902_000_000,
            band_stop_hz=928_000_000,
            max_gain_db=30,
            ttl_seconds=1800,
        )
        active = await permissions.list_active(kind="tx")
        assert len(active) == 2
