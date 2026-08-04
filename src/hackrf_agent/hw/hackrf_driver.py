"""Async context manager wrapping a single libhackrf device handle.

Usage::

    stop = asyncio.Event()
    async with HackrfDriver(stop_event=stop) as drv:
        info = await drv.get_device_info()
        spec, freqs = await drv.sweep_spectrum(...)

Not thread-safe. One instance per open device. Second concurrent
``__aenter__`` raises ``HackrfBusyError``.

The pyhackrf API validated against: **pyhackrf 0.2.x** (exact version
TBD — verify with ``pip show pyhackrf`` and update comments below).
"""

from __future__ import annotations

import asyncio
import queue
from pathlib import Path
from typing import Any, Final

import numpy as np
import numpy.typing as npt

from hackrf_agent.domain.models import DeviceInfo
from hackrf_agent.hw.dsp import (
    fft_freq_axis,
    fft_magnitude_db,
    iq_to_complex64,
)
from hackrf_agent.hw.exceptions import (
    HackrfBusyError,
    HackrfError,
    HackrfNotFoundError,
    InvalidHackrfArgError,
    KillSwitchTriggered,
)

# ---------------------------------------------------------------------------
# libhackrf-supported sample rates in Hz.
# ---------------------------------------------------------------------------

VALID_SAMPLE_RATES_HZ: Final[tuple[int, ...]] = (
    2_000_000,
    4_000_000,
    8_000_000,
    10_000_000,
    12_500_000,
    16_000_000,
    20_000_000,
)

# ---------------------------------------------------------------------------
# Gain grids. Value MUST be exactly on-grid or the driver rejects.
# ---------------------------------------------------------------------------

VALID_RF_AMP_DB: Final[tuple[int, ...]] = (0, 14)
VALID_LNA_GAIN_DB: Final[tuple[int, ...]] = tuple(range(0, 41, 8))  # 0,8,16,24,32,40
VALID_RX_VGA_GAIN_DB: Final[tuple[int, ...]] = tuple(range(0, 63, 2))  # 0,2,4,...,62
VALID_TX_VGA_GAIN_DB: Final[tuple[int, ...]] = tuple(range(0, 48, 1))  # 0..47

# ---------------------------------------------------------------------------
# HackRF One tunable range.
# ---------------------------------------------------------------------------

MIN_FREQ_HZ: Final[int] = 1_000_000  # 1 MHz
MAX_FREQ_HZ: Final[int] = 6_000_000_000  # 6 GHz

# ---------------------------------------------------------------------------
# libhackrf's default USB transfer size (bytes of int8 IQ, i.e., 131072 samples).
# ---------------------------------------------------------------------------

DEFAULT_BUFFER_BYTES: Final[int] = 262_144


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_center_freq(center_hz: int) -> None:
    """Raise ``InvalidHackrfArgError`` if *center_hz* is outside the HackRF tunable range."""
    if not (MIN_FREQ_HZ <= center_hz <= MAX_FREQ_HZ):
        raise InvalidHackrfArgError(
            f"center_hz {center_hz} outside HackRF tunable range [{MIN_FREQ_HZ}, {MAX_FREQ_HZ}]"
        )


def _validate_sample_rate(rate_hz: int) -> None:
    """Raise ``InvalidHackrfArgError`` if *rate_hz* is not a valid HackRF sample rate."""
    if rate_hz not in VALID_SAMPLE_RATES_HZ:
        raise InvalidHackrfArgError(f"sample_rate {rate_hz} Hz not on grid {VALID_SAMPLE_RATES_HZ}")


def _validate_gain(name: str, value: int, grid: tuple[int, ...]) -> None:
    """Raise ``InvalidHackrfArgError`` if *value* is not exactly on *grid*."""
    if value not in grid:
        raise InvalidHackrfArgError(f"{name}={value} not on grid {grid}")


# ---------------------------------------------------------------------------
# HackrfDriver
# ---------------------------------------------------------------------------


class HackrfDriver:
    """Async context manager wrapping a single libhackrf device handle.

    Usage::

        stop = asyncio.Event()
        async with HackrfDriver(stop_event=stop) as drv:
            info = await drv.get_device_info()
            spec, freqs = await drv.sweep_spectrum(...)

    Not thread-safe. One instance per open device. Second concurrent
    ``__aenter__`` raises ``HackrfBusyError``.
    """

    def __init__(
        self,
        *,
        stop_event: asyncio.Event,
        buffer_bytes: int = DEFAULT_BUFFER_BYTES,
    ) -> None:
        self._stop_event = stop_event
        self._buffer_bytes = buffer_bytes
        self._device: Any = None  # pyhackrf device handle (Any: optional dep)
        self._lib: Any = None  # imported lazily in __aenter__ (Any: optional dep)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> HackrfDriver:
        # Lazy import so tests without pyhackrf installed can still import
        # the module for symbol inspection.
        try:
            import pyhackrf  # noqa: PLC0415  # pyright: ignore[reportMissingImports]
        except ImportError as e:
            raise HackrfNotFoundError(
                "pyhackrf not installed; run `pip install hackrf-agent[hackrf]`"
            ) from e

        self._lib = pyhackrf

        try:
            # pyhackrf v0.2.x — module-level init/open.  Verify after install.
            self._lib.pyhackrf_init()
            self._device = self._lib.pyhackrf_open()
        except Exception as e:
            # pyhackrf raises its own exception types; classify by message.
            msg = str(e).lower()
            if "not found" in msg or "no device" in msg:
                raise HackrfNotFoundError(str(e)) from e
            if "busy" in msg or "claim" in msg:
                raise HackrfBusyError(str(e)) from e
            raise HackrfError(f"pyhackrf_open failed: {e}") from e

        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._device is not None:
            try:
                # pyhackrf v0.2.x
                self._lib.pyhackrf_close(self._device)
            finally:
                self._device = None
        if self._lib is not None:
            try:
                # pyhackrf v0.2.x
                self._lib.pyhackrf_exit()
            finally:
                self._lib = None

    # ------------------------------------------------------------------
    # Kill-switch check
    # ------------------------------------------------------------------

    def _check_stop(self) -> None:
        """Raise ``KillSwitchTriggered`` if the shared stop event is set."""
        if self._stop_event.is_set():
            raise KillSwitchTriggered("stop_event set")

    # ------------------------------------------------------------------
    # Public API — device info
    # ------------------------------------------------------------------

    async def get_device_info(self) -> DeviceInfo:
        """Return the connected device's identity fields."""
        self._check_stop()
        if self._device is None:
            raise HackrfError("device not opened")

        loop = asyncio.get_running_loop()
        try:
            # pyhackrf v0.2.x board-info accessors — verify after install.
            info: dict[str, object] = await loop.run_in_executor(
                None,
                lambda: {
                    "serial": self._lib.pyhackrf_board_id_read(self._device),
                    "firmware_version": self._lib.pyhackrf_version_string_read(self._device),
                    "board_revision": self._lib.pyhackrf_board_rev_read(self._device),
                    "part_id": self._lib.pyhackrf_board_partid_serialno_read(self._device),
                },
            )
        except Exception as e:
            raise HackrfError(f"reading board info failed: {e}") from e

        return DeviceInfo(
            serial=str(info["serial"]),
            firmware_version=str(info["firmware_version"]),
            board_revision=str(info["board_revision"]),
            part_id=str(info["part_id"]),
        )

    # ------------------------------------------------------------------
    # Public API — sweep spectrum (RX only)
    # ------------------------------------------------------------------

    async def sweep_spectrum(
        self,
        *,
        start_hz: int,
        stop_hz: int,
        sample_rate_hz: int,
        lna_gain_db: int = 16,
        vga_gain_db: int = 20,
        rf_amp_db: int = 0,
        dwell_s: float = 1.0,
        fft_size: int = 4096,
    ) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.float64]]:
        """RX-only sweep across [start_hz, stop_hz].

        For the day-1 implementation we tune to ``(start+stop)//2``, sample
        at ``sample_rate_hz`` for ``dwell_s``, and return one FFT centered
        there. If ``(stop-start) > sample_rate_hz`` the tail of the
        requested range falls outside the captured bandwidth — the
        executor (Part 5) is responsible for detecting that.

        Multi-tune sweeping (``hackrf_sweep``-style) is deferred.

        Returns:
            ``(magnitude_db, freqs_hz)`` — both shape ``(fft_size,)``.
        """
        self._check_stop()
        center_hz = (start_hz + stop_hz) // 2
        _validate_center_freq(center_hz)
        _validate_sample_rate(sample_rate_hz)
        _validate_gain("lna_gain_db", lna_gain_db, VALID_LNA_GAIN_DB)
        _validate_gain("vga_gain_db (RX)", vga_gain_db, VALID_RX_VGA_GAIN_DB)
        _validate_gain("rf_amp_db", rf_amp_db, VALID_RF_AMP_DB)

        if start_hz >= stop_hz:
            raise InvalidHackrfArgError("start_hz must be < stop_hz")
        if not (0.0 < dwell_s <= 30.0):
            raise InvalidHackrfArgError(f"dwell_s {dwell_s} outside (0, 30]s")

        num_samples = int(sample_rate_hz * dwell_s)
        iq_bytes = await self._rx_bytes(
            center_hz=center_hz,
            sample_rate_hz=sample_rate_hz,
            num_samples=num_samples,
            lna_gain_db=lna_gain_db,
            vga_gain_db=vga_gain_db,
            rf_amp_db=rf_amp_db,
        )

        # DSP off the USB thread — already on the asyncio side here.
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: (
                fft_magnitude_db(iq_to_complex64(iq_bytes), fft_size),
                fft_freq_axis(center_hz, sample_rate_hz, fft_size),
            ),
        )

    # ------------------------------------------------------------------
    # Public API — capture IQ to disk
    # ------------------------------------------------------------------

    async def capture_iq(
        self,
        *,
        center_hz: int,
        sample_rate_hz: int,
        num_samples: int,
        lna_gain_db: int = 16,
        vga_gain_db: int = 20,
        rf_amp_db: int = 0,
        out_path: Path,
    ) -> Path:
        """Capture raw IQ to disk in libhackrf's native int8 interleaved format.

        Returns the path written. Raises if:

        * ``out_path`` exists and is not an empty file (no clobber).
        * Validation of freq/rate/gain fails.
        * libhackrf errors during the transfer.
        """
        self._check_stop()
        _validate_center_freq(center_hz)
        _validate_sample_rate(sample_rate_hz)
        _validate_gain("lna_gain_db", lna_gain_db, VALID_LNA_GAIN_DB)
        _validate_gain("vga_gain_db (RX)", vga_gain_db, VALID_RX_VGA_GAIN_DB)
        _validate_gain("rf_amp_db", rf_amp_db, VALID_RF_AMP_DB)

        if num_samples <= 0:
            raise InvalidHackrfArgError(f"num_samples {num_samples} must be > 0")

        if out_path.exists() and out_path.stat().st_size > 0:
            raise InvalidHackrfArgError(f"refusing to clobber non-empty file: {out_path}")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        iq_bytes = await self._rx_bytes(
            center_hz=center_hz,
            sample_rate_hz=sample_rate_hz,
            num_samples=num_samples,
            lna_gain_db=lna_gain_db,
            vga_gain_db=vga_gain_db,
            rf_amp_db=rf_amp_db,
        )

        # Write on a thread — sync file I/O off the event loop.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: out_path.write_bytes(iq_bytes))
        return out_path

    # ------------------------------------------------------------------
    # Public API — transmit IQ (wired but not yet CLI-exposed)
    # ------------------------------------------------------------------

    async def transmit_iq(
        self,
        *,
        center_hz: int,
        sample_rate_hz: int,
        iq_path: Path,
        txvga_gain_db: int,
        rf_amp_db: int = 0,
    ) -> None:
        """Transmit a pre-recorded int8 interleaved IQ file.

        Blocks until the file is fully sent or the kill switch fires.
        Callers upstream (Part 5) MUST have already run this through the
        risk assessor. The driver only validates hardware-grid arguments.
        """
        self._check_stop()
        _validate_center_freq(center_hz)
        _validate_sample_rate(sample_rate_hz)
        _validate_gain("txvga_gain_db", txvga_gain_db, VALID_TX_VGA_GAIN_DB)
        _validate_gain("rf_amp_db", rf_amp_db, VALID_RF_AMP_DB)

        if not iq_path.is_file():
            raise InvalidHackrfArgError(f"iq_path is not a file: {iq_path}")
        if iq_path.stat().st_size == 0:
            raise InvalidHackrfArgError(f"iq_path is empty: {iq_path}")
        if iq_path.stat().st_size % 2 != 0:
            raise InvalidHackrfArgError(
                f"iq_path size {iq_path.stat().st_size} is odd — I/Q pair mismatch"
            )

        await self._tx_from_file(
            center_hz=center_hz,
            sample_rate_hz=sample_rate_hz,
            iq_path=iq_path,
            txvga_gain_db=txvga_gain_db,
            rf_amp_db=rf_amp_db,
        )

    # ------------------------------------------------------------------
    # Private — RX callback bridge
    # ------------------------------------------------------------------

    async def _rx_bytes(
        self,
        *,
        center_hz: int,
        sample_rate_hz: int,
        num_samples: int,
        lna_gain_db: int,
        vga_gain_db: int,
        rf_amp_db: int,
    ) -> bytes:
        """Start RX, accumulate *num_samples* int8 I/Q pairs, stop RX.

        The RX callback runs on libhackrf's USB thread. It pushes chunks
        into a plain ``queue.Queue`` (thread-safe). This coroutine drains
        the queue via ``run_in_executor`` and stitches chunks together.
        """
        assert self._device is not None
        loop = asyncio.get_running_loop()
        target_bytes = num_samples * 2
        chunks: queue.Queue[bytes | None] = queue.Queue()
        received: list[bytes] = []
        received_len = 0

        def rx_callback(transfer: Any) -> int:
            # ONLY do buffer copy. No numpy, no lock contention.
            if self._stop_event.is_set():
                chunks.put(None)  # sentinel; drain-side will stop
                return -1  # tell libhackrf to stop pumping
            # pyhackrf v0.2.x — transfer.buffer_as_bytes() returns the raw
            # USB transfer buffer as bytes.  Verify after install.
            buf = bytes(transfer.buffer_as_bytes())
            chunks.put(buf)
            return 0

        # Configure device.
        await loop.run_in_executor(
            None,
            self._configure_rx,
            center_hz,
            sample_rate_hz,
            lna_gain_db,
            vga_gain_db,
            rf_amp_db,
        )

        try:
            # pyhackrf v0.2.x — start_rx(device, callback).
            await loop.run_in_executor(
                None,
                lambda: self._lib.pyhackrf_start_rx(self._device, rx_callback),
            )

            # Drain until we have enough bytes or kill switch fires.
            while received_len < target_bytes:
                chunk = await loop.run_in_executor(None, chunks.get)
                if chunk is None:
                    raise KillSwitchTriggered("stop_event set during RX")
                received.append(chunk)
                received_len += len(chunk)
        finally:
            # pyhackrf v0.2.x
            await loop.run_in_executor(
                None,
                lambda: self._lib.pyhackrf_stop_rx(self._device),
            )

        # Concatenate and trim to exact requested length.
        raw = b"".join(received)[:target_bytes]
        return raw

    # ------------------------------------------------------------------
    # Private — RX device configuration
    # ------------------------------------------------------------------

    def _configure_rx(
        self,
        center_hz: int,
        sample_rate_hz: int,
        lna_gain_db: int,
        vga_gain_db: int,
        rf_amp_db: int,
    ) -> None:
        """Configure the HackRF for RX — runs on an executor thread."""
        # Order matches libhackrf's expected setup sequence.
        # pyhackrf v0.2.x — verify function names after install.
        self._lib.pyhackrf_set_sample_rate(self._device, sample_rate_hz)
        self._lib.pyhackrf_set_baseband_filter_bandwidth(
            self._device,
            self._lib.pyhackrf_compute_baseband_filter_bw(sample_rate_hz),
        )
        self._lib.pyhackrf_set_freq(self._device, center_hz)
        self._lib.pyhackrf_set_amp_enable(self._device, 1 if rf_amp_db else 0)
        self._lib.pyhackrf_set_lna_gain(self._device, lna_gain_db)
        self._lib.pyhackrf_set_vga_gain(self._device, vga_gain_db)

    # ------------------------------------------------------------------
    # Private — TX from file
    # ------------------------------------------------------------------

    async def _tx_from_file(
        self,
        *,
        center_hz: int,
        sample_rate_hz: int,
        iq_path: Path,
        txvga_gain_db: int,
        rf_amp_db: int,
    ) -> None:
        """Mirror of ``_rx_bytes`` for TX.

        Reads chunks from *iq_path* and feeds them to libhackrf's TX
        callback.  Blocks until EOF or kill switch.
        """
        assert self._device is not None
        loop = asyncio.get_running_loop()

        # Open file on a thread.
        file_handle = await loop.run_in_executor(None, lambda: iq_path.open("rb"))
        try:

            def tx_callback(transfer: Any) -> int:
                if self._stop_event.is_set():
                    return -1
                # pyhackrf v0.2.x — transfer.buffer_length tells us how
                # many bytes libhackrf can accept this invocation.
                needed = transfer.buffer_length
                chunk = file_handle.read(needed)
                if not chunk:
                    return -1  # EOF; libhackrf stops
                # pyhackrf v0.2.x — write_buffer_bytes fills the transfer.
                transfer.write_buffer_bytes(chunk)
                return 0

            await loop.run_in_executor(
                None,
                self._configure_tx,
                center_hz,
                sample_rate_hz,
                txvga_gain_db,
                rf_amp_db,
            )

            done_event = asyncio.Event()

            def on_stopped() -> None:
                loop.call_soon_threadsafe(done_event.set)

            # pyhackrf v0.2.x — start_tx(device, callback, stopped_callback).
            await loop.run_in_executor(
                None,
                lambda: self._lib.pyhackrf_start_tx(self._device, tx_callback, on_stopped),
            )
            await done_event.wait()
        finally:
            file_handle.close()
            # pyhackrf v0.2.x
            await loop.run_in_executor(
                None,
                lambda: self._lib.pyhackrf_stop_tx(self._device),
            )

        if self._stop_event.is_set():
            raise KillSwitchTriggered("stop_event set during TX")

    # ------------------------------------------------------------------
    # Private — TX device configuration
    # ------------------------------------------------------------------

    def _configure_tx(
        self,
        center_hz: int,
        sample_rate_hz: int,
        txvga_gain_db: int,
        rf_amp_db: int,
    ) -> None:
        """Configure the HackRF for TX — runs on an executor thread."""
        # pyhackrf v0.2.x — verify function names after install.
        self._lib.pyhackrf_set_sample_rate(self._device, sample_rate_hz)
        self._lib.pyhackrf_set_baseband_filter_bandwidth(
            self._device,
            self._lib.pyhackrf_compute_baseband_filter_bw(sample_rate_hz),
        )
        self._lib.pyhackrf_set_freq(self._device, center_hz)
        self._lib.pyhackrf_set_amp_enable(self._device, 1 if rf_amp_db else 0)
        self._lib.pyhackrf_set_txvga_gain(self._device, txvga_gain_db)
