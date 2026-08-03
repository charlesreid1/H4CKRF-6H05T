"""Hardware integration tests for HackrfDriver.

All tests are marked ``@pytest.mark.hardware`` and skipped unless
``pytest --hardware`` is passed. These require a HackRF One plugged in
via USB.

**Never TX in CI.** No ``transmit_iq`` in automated tests, ever.
"""

import asyncio

import numpy as np
import pytest

from hackrf_agent.hw.exceptions import KillSwitchTriggered
from hackrf_agent.hw.hackrf_driver import HackrfDriver

pytestmark = pytest.mark.hardware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _requires_hardware():
    """Skip if --hardware was not passed."""
    pass  # handled by pytestmark


# ======================================================================
# Device enumeration
# ======================================================================


@pytest.mark.asyncio
async def test_get_device_info():
    """``get_device_info`` returns a non-empty serial string."""
    stop = asyncio.Event()
    async with HackrfDriver(stop_event=stop) as drv:
        info = await drv.get_device_info()

    assert info.serial, f"expected non-empty serial, got {info.serial!r}"
    assert info.firmware_version, "expected non-empty firmware_version"
    assert info.board_revision, "expected non-empty board_revision"


# ======================================================================
# Sweep spectrum RX
# ======================================================================


@pytest.mark.asyncio
async def test_sweep_spectrum_returns_expected_shape():
    """A 100 ms sweep of the 433 MHz ISM band returns two (4096,) arrays."""
    stop = asyncio.Event()
    async with HackrfDriver(stop_event=stop) as drv:
        mag_db, freqs_hz = await drv.sweep_spectrum(
            start_hz=433_000_000,
            stop_hz=434_000_000,
            sample_rate_hz=2_000_000,
            dwell_s=0.1,
        )

    assert isinstance(mag_db, np.ndarray)
    assert isinstance(freqs_hz, np.ndarray)
    assert mag_db.shape == (4096,), f"expected (4096,), got {mag_db.shape}"
    assert freqs_hz.shape == (4096,), f"expected (4096,), got {freqs_hz.shape}"
    assert mag_db.dtype == np.float32, f"expected float32, got {mag_db.dtype}"
    assert freqs_hz.dtype == np.float64, f"expected float64, got {freqs_hz.dtype}"


# ======================================================================
# Kill-switch
# ======================================================================


@pytest.mark.asyncio
async def test_kill_switch_aborts_sweep():
    """Setting stop_event during a sweep raises KillSwitchTriggered quickly."""
    stop = asyncio.Event()

    async with HackrfDriver(stop_event=stop) as drv:
        # Start a longer sweep in a background task.
        async def long_sweep():
            return await drv.sweep_spectrum(
                start_hz=433_000_000,
                stop_hz=434_000_000,
                sample_rate_hz=2_000_000,
                dwell_s=5.0,
            )

        task = asyncio.create_task(long_sweep())

        # Give the sweep time to start RX.
        await asyncio.sleep(0.1)

        # Fire the kill switch.
        stop.set()

        # The task should raise KillSwitchTriggered promptly.
        with pytest.raises(KillSwitchTriggered):
            await asyncio.wait_for(task, timeout=2.0)
