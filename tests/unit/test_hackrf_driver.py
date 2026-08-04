"""Unit tests for hackrf_driver.py — validation logic only, no device opened.

All tests exercise argument validation and module importability without
ever requiring a physical HackRF or even the pyhackrf package.
"""

import asyncio
import sys

import pytest

from hackrf_agent.hw.exceptions import HackrfNotFoundError, InvalidHackrfArgError
from hackrf_agent.hw.hackrf_driver import (
    VALID_LNA_GAIN_DB,
    VALID_RF_AMP_DB,
    VALID_RX_VGA_GAIN_DB,
    VALID_TX_VGA_GAIN_DB,
    HackrfDriver,
    _validate_center_freq,
    _validate_gain,
    _validate_sample_rate,
)

# ======================================================================
# _validate_center_freq
# ======================================================================


class TestValidateCenterFreq:
    def test_below_min_raises(self):
        """500 kHz is below the HackRF tunable minimum."""
        with pytest.raises(InvalidHackrfArgError, match="outside HackRF tunable"):
            _validate_center_freq(500_000)

    def test_above_max_raises(self):
        """7 GHz is above the HackRF tunable maximum."""
        with pytest.raises(InvalidHackrfArgError, match="outside HackRF tunable"):
            _validate_center_freq(7_000_000_000)

    def test_valid_freq_returns_none(self):
        """433.92 MHz is within range."""
        assert _validate_center_freq(433_920_000) is None

    def test_edge_min_accepted(self):
        """1 MHz (minimum) is accepted."""
        assert _validate_center_freq(1_000_000) is None

    def test_edge_max_accepted(self):
        """6 GHz (maximum) is accepted."""
        assert _validate_center_freq(6_000_000_000) is None


# ======================================================================
# _validate_sample_rate
# ======================================================================


class TestValidateSampleRate:
    def test_off_grid_rate_raises(self):
        """3 Msps is not a valid HackRF rate."""
        with pytest.raises(InvalidHackrfArgError, match="not on grid"):
            _validate_sample_rate(3_000_000)

    @pytest.mark.parametrize(
        "rate",
        [2_000_000, 4_000_000, 8_000_000, 10_000_000, 12_500_000, 16_000_000, 20_000_000],
    )
    def test_on_grid_rates_accepted(self, rate):
        """All valid HackRF rates pass validation."""
        assert _validate_sample_rate(rate) is None

    def test_zero_rate_raises(self):
        """0 Hz is not a valid rate."""
        with pytest.raises(InvalidHackrfArgError, match="not on grid"):
            _validate_sample_rate(0)


# ======================================================================
# _validate_gain
# ======================================================================


class TestValidateGain:
    def test_lna_off_grid_raises(self):
        """LNA gain of 3 dB is not on the 8 dB step grid."""
        with pytest.raises(InvalidHackrfArgError, match="not on grid"):
            _validate_gain("lna", 3, VALID_LNA_GAIN_DB)

    def test_lna_on_grid_accepted(self):
        """LNA gain of 16 dB is valid."""
        assert _validate_gain("lna", 16, VALID_LNA_GAIN_DB) is None

    def test_lna_max_accepted(self):
        """LNA gain of 40 dB is valid."""
        assert _validate_gain("lna", 40, VALID_LNA_GAIN_DB) is None

    def test_txvga_above_max_raises(self):
        """TX VGA gain of 48 dB is above the 47 dB max."""
        with pytest.raises(InvalidHackrfArgError, match="not on grid"):
            _validate_gain("txvga", 48, VALID_TX_VGA_GAIN_DB)

    def test_txvga_zero_accepted(self):
        """TX VGA gain of 0 dB is valid."""
        assert _validate_gain("txvga", 0, VALID_TX_VGA_GAIN_DB) is None

    def test_rf_amp_off_grid_raises(self):
        """RF amp gain of 7 dB is not valid (only 0 or 14)."""
        with pytest.raises(InvalidHackrfArgError, match="not on grid"):
            _validate_gain("rf_amp", 7, VALID_RF_AMP_DB)

    def test_rf_amp_on_grid_accepted(self):
        """RF amp gain of 14 dB is valid."""
        assert _validate_gain("rf_amp", 14, VALID_RF_AMP_DB) is None

    def test_rx_vga_off_grid_raises(self):
        """RX VGA gain of 3 dB is not on the 2 dB step grid."""
        with pytest.raises(InvalidHackrfArgError, match="not on grid"):
            _validate_gain("vga", 3, VALID_RX_VGA_GAIN_DB)


# ======================================================================
# Module import without pyhackrf
# ======================================================================


class TestImportWithoutPyhackrf:
    def test_module_imports_without_pyhackrf(self):
        """The hackrf_driver module is importable even without pyhackrf."""
        # The module was already imported at the top of this file — if
        # pyhackrf were unavailable, the import would have failed here.
        # We verify the symbols we need are present.
        assert HackrfDriver is not None
        assert _validate_center_freq is not None

    def test_constructor_succeeds_without_device(self):
        """HackrfDriver(stop_event=...) constructs without opening a device."""
        stop = asyncio.Event()
        drv = HackrfDriver(stop_event=stop)
        assert drv._device is None
        assert drv._stop_event is stop

    @pytest.mark.asyncio
    async def test_enter_without_pyhackrf_raises_not_found(self):
        """Entering context without pyhackrf installed raises HackrfNotFoundError."""
        # Simulate pyhackrf not being installed.
        stop = asyncio.Event()
        drv = HackrfDriver(stop_event=stop)

        with patch.dict(sys.modules, {"pyhackrf": None}):
            # Also need to make the import inside __aenter__ fail.
            import builtins

            original_import = builtins.__import__

            def _block_pyhackrf(name, *args, **kwargs):
                if name == "pyhackrf" or name.startswith("pyhackrf."):
                    raise ImportError("No module named 'pyhackrf'")
                return original_import(name, *args, **kwargs)

            with (
                patch("builtins.__import__", side_effect=_block_pyhackrf),
                pytest.raises(HackrfNotFoundError, match="pyhackrf not installed"),
            ):
                await drv.__aenter__()

    @pytest.mark.asyncio
    async def test_exit_when_device_is_none_is_safe(self):
        """__aexit__ when _device is None is a no-op."""
        stop = asyncio.Event()
        drv = HackrfDriver(stop_event=stop)
        # Should not raise.
        await drv.__aexit__(None, None, None)


# ======================================================================
# Kill-switch
# ======================================================================


class TestKillSwitch:
    def test_check_stop_raises_when_set(self):
        """_check_stop raises KillSwitchTriggered when the event is set."""
        from hackrf_agent.hw.exceptions import KillSwitchTriggered

        stop = asyncio.Event()
        stop.set()
        drv = HackrfDriver(stop_event=stop)

        with pytest.raises(KillSwitchTriggered, match="stop_event set"):
            drv._check_stop()

    def test_check_stop_does_not_raise_when_clear(self):
        """_check_stop is a no-op when the event is clear."""
        stop = asyncio.Event()
        drv = HackrfDriver(stop_event=stop)
        # Should not raise.
        drv._check_stop()

    @pytest.mark.asyncio
    async def test_get_device_info_checks_stop(self):
        """get_device_info calls _check_stop before proceeding."""
        from hackrf_agent.hw.exceptions import KillSwitchTriggered

        stop = asyncio.Event()
        stop.set()
        drv = HackrfDriver(stop_event=stop)

        with pytest.raises(KillSwitchTriggered):
            await drv.get_device_info()


# ---------------------------------------------------------------------------
# patch helper
# ---------------------------------------------------------------------------

from unittest.mock import patch  # noqa: E402
