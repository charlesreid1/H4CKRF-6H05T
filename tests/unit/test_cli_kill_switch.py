"""Unit tests for :mod:`hackrf_agent.cli.kill_switch`."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from hackrf_agent.cli.kill_switch import DOUBLE_TAP_WINDOW_S, KillSwitch
from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.permission_service import PermissionService

# -- helpers -----------------------------------------------------------------


def _make_mock_perms(*, revoke_all_tx_return: int = 0) -> Mock:
    """Return a PermissionService mock whose ``revoke_all_tx()`` returns
    *revoke_all_tx_return* (an int) and whose other methods are harmless
    stubs.
    """
    m = Mock(spec=PermissionService)
    m.revoke_all_tx = AsyncMock(return_value=revoke_all_tx_return)
    return m


# -- tests --------------------------------------------------------------------


class TestKillSwitchFirstPress:
    """Tests for the first-SIGINT behavior."""

    @pytest.mark.asyncio
    async def test_stop_event_set_on_first_sigint(self) -> None:
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        perms = _make_mock_perms()
        ks = KillSwitch(stop_event=stop_event, permissions=perms)
        assert not stop_event.is_set()
        ks._on_sigint(loop)
        assert stop_event.is_set()

    @pytest.mark.asyncio
    async def test_revoke_tx_called_on_first_sigint(
        self, tmp_path
    ) -> None:
        db = tmp_path / "test.db"
        await ensure_schema(db)
        perms = PermissionService(db)
        # Pre-grant a TX so we have something to revoke.
        await perms.grant(
            kind="tx",
            band_start_hz=433_000_000,
            band_stop_hz=435_000_000,
            max_gain_db=20,
            ttl_seconds=3600,
        )
        active_before = await perms.list_active()
        assert len(active_before) == 1

        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        ks = KillSwitch(stop_event=stop_event, permissions=perms)
        ks._on_sigint(loop)
        # Let the fire-and-forget revoke task run.
        await asyncio.sleep(0.05)

        active_after = await perms.list_active()
        assert len(active_after) == 0


class TestKillSwitchDoubleTap:
    """Tests for the double-Ctrl-C hard-exit behavior."""

    @pytest.mark.asyncio
    async def test_double_tap_stops_loop(self) -> None:
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        perms = _make_mock_perms()
        ks = KillSwitch(stop_event=stop_event, permissions=perms)

        # Replace loop.stop with a spy so we can assert it was called.
        stop_called = False
        _original_stop = loop.stop

        def _stop_spy():
            nonlocal stop_called
            stop_called = True

        loop.stop = _stop_spy  # type: ignore[method-assign]

        try:
            # First press.
            ks._on_sigint(loop)
            assert not stop_called  # first press does NOT stop

            # Second press — still within window (time.monotonic hasn't advanced).
            ks._on_sigint(loop)
            assert stop_called  # second press STOPS
        finally:
            loop.stop = _original_stop  # type: ignore[method-assign]

    @pytest.mark.asyncio
    async def test_double_tap_expired_window_treated_as_first(
        self, monkeypatch
    ) -> None:
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        perms = _make_mock_perms()
        ks = KillSwitch(stop_event=stop_event, permissions=perms)

        # Freeze time.monotonic at 100.0.
        t0 = 100.0
        monkeypatch.setattr("time.monotonic", lambda: t0)

        # First press at t=100.0.
        ks._on_sigint(loop)
        assert stop_event.is_set()

        # Advance past the double-tap window.
        t0 += DOUBLE_TAP_WINDOW_S + 0.1
        # Reset for the second "first press".
        stop_event.clear()
        ks._on_sigint(loop)
        # Second press is also treated as first-press (stop_event set again).
        assert stop_event.is_set()


class TestKillSwitchInstallUninstall:
    """Tests for install_handler / uninstall_handler."""

    @pytest.mark.asyncio
    async def test_install_twice_is_idempotent(self) -> None:
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        perms = _make_mock_perms()
        ks = KillSwitch(stop_event=stop_event, permissions=perms)
        ks.install_handler(loop)
        ks.install_handler(loop)  # second call should not raise
        assert ks._installed is True
        ks.uninstall_handler(loop)

    @pytest.mark.asyncio
    async def test_uninstall_twice_is_idempotent(self) -> None:
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        perms = _make_mock_perms()
        ks = KillSwitch(stop_event=stop_event, permissions=perms)
        ks.install_handler(loop)
        ks.uninstall_handler(loop)
        assert ks._installed is False
        ks.uninstall_handler(loop)  # second call should not raise

    @pytest.mark.asyncio
    async def test_idempotent_stop_event_set(self, monkeypatch) -> None:
        """Calling _on_sigint when stop_event is already set is idempotent."""
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        perms = _make_mock_perms()
        ks = KillSwitch(stop_event=stop_event, permissions=perms)

        # Freeze time to prevent double-tap detection on second call.
        t0 = 100.0
        monkeypatch.setattr("time.monotonic", lambda: t0)
        ks._on_sigint(loop)
        assert stop_event.is_set()

        # Advance past the double-tap window so this is a fresh first-press.
        t0 += DOUBLE_TAP_WINDOW_S + 0.1
        ks._on_sigint(loop)
        assert stop_event.is_set()  # still set
        # Let fire-and-forget tasks drain.
        await asyncio.sleep(0)
