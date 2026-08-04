"""Async context manager wrapping a single libhackrf device handle.

Usage::

    stop = asyncio.Event()
    async with HackrfDriver(stop_event=stop) as drv:
        info = await drv.get_device_info()
        spec, freqs = await drv.sweep_spectrum(...)

Not thread-safe. One instance per open device. Second concurrent
``__aenter__`` raises ``HackrfBusyError``.

Backed by **python-hackrf 1.5.x** (``from python_hackrf import pyhackrf``).
Module-level ``pyhackrf_init``/``pyhackrf_exit``/``pyhackrf_open`` open a
``PyHackrfDevice`` whose per-device operations are instance methods.
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
        self._device: Any = None  # PyHackrfDevice handle (Any: optional dep)
        self._lib: Any = None  # imported lazily in __aenter__ (Any: optional dep)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> HackrfDriver:
        try:
            from python_hackrf import pyhackrf  # noqa: PLC0415  # pyright: ignore[reportMissingImports]
        except ImportError as e:
            raise HackrfNotFoundError(
                "python-hackrf not installed; run `pip install hackrf-agent[hackrf]`"
            ) from e

        self._lib = pyhackrf

        try:
            self._lib.pyhackrf_init()
            device = self._lib.pyhackrf_open()
        except self._lib.PYHACKRF_ERROR_NOT_FOUND as e:
            raise HackrfNotFoundError(str(e)) from e
        except self._lib.PYHACKRF_ERROR_BUSY as e:
            raise HackrfBusyError(str(e)) from e
        except self._lib.PYHACKRF_ERR as e:
            raise HackrfError(f"pyhackrf_open failed: {e}") from e

        if device is None:
            raise HackrfNotFoundError("pyhackrf_open returned None (no device attached)")

        self._device = device
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._device is not None:
            try:
                self._device.pyhackrf_close()
            finally:
                self._device = None
        if self._lib is not None:
            try:
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
            info = await loop.run_in_executor(None, self._read_board_info)
        except Exception as e:
            raise HackrfError(f"reading board info failed: {e}") from e

        return info

    def _read_board_info(self) -> DeviceInfo:
        """Read and normalize the device's board-info tuple returns."""
        # board_id_read -> (int, str);  we want the human-readable string.
        _board_id_int, board_id_name = self._device.pyhackrf_board_id_read()
        # board_rev_read -> (int, str)
        _rev_int, board_rev_name = self._device.pyhackrf_board_rev_read()
        firmware = self._device.pyhackrf_version_string_read()
        # board_partid_serialno_read -> ((int, int), (int, int, int, int))
        part_id_pair, serialno_words = self._device.pyhackrf_board_partid_serialno_read()

        part_id_str = " ".join(f"0x{w:08x}" for w in part_id_pair)
        serial_str = "".join(f"{w:08x}" for w in serialno_words)

        return DeviceInfo(
            serial=serial_str,
            firmware_version=str(firmware),
            board_revision=str(board_rev_name),
            part_id=part_id_str,
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

        The RX callback runs on libhackrf's USB thread. It copies each
        buffer into a plain ``queue.Queue`` (thread-safe). This coroutine
        drains the queue via ``run_in_executor`` and stitches chunks.
        """
        assert self._device is not None
        loop = asyncio.get_running_loop()
        target_bytes = num_samples * 2
        chunks: queue.Queue[bytes | None] = queue.Queue()

        def rx_callback(
            device: Any,
            buffer: np.ndarray,  # dtype=int8
            _buffer_length: int,
            valid_length: int,
        ) -> int:
            # ONLY do buffer copy. No FFT, no lock contention.
            if self._stop_event.is_set():
                chunks.put(None)  # sentinel; drain-side will stop
                return -1  # tell libhackrf to stop pumping
            # Copy `valid_length` int8 samples to an owned bytes object.
            chunks.put(buffer[:valid_length].tobytes())
            return 0

        # Configure device, register callback.
        await loop.run_in_executor(
            None,
            self._configure_rx,
            center_hz,
            sample_rate_hz,
            lna_gain_db,
            vga_gain_db,
            rf_amp_db,
        )
        await loop.run_in_executor(None, self._device.set_rx_callback, rx_callback)

        received: list[bytes] = []
        received_len = 0
        try:
            await loop.run_in_executor(None, self._device.pyhackrf_start_rx)

            # Drain until we have enough bytes or kill switch fires.
            while received_len < target_bytes:
                chunk = await loop.run_in_executor(None, chunks.get)
                if chunk is None:
                    raise KillSwitchTriggered("stop_event set during RX")
                received.append(chunk)
                received_len += len(chunk)
        finally:
            try:
                await loop.run_in_executor(None, self._device.pyhackrf_stop_rx)
            except Exception:  # noqa: BLE001 — best-effort stop on already-stopped device
                pass

        # Concatenate and trim to exact requested length.
        return b"".join(received)[:target_bytes]

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
        # NOTE: pyhackrf_set_sample_rate() also resets the baseband filter
        # bandwidth to 0.75 * sample_rate, so set the filter AFTER the rate.
        self._device.pyhackrf_set_sample_rate(sample_rate_hz)
        self._device.pyhackrf_set_baseband_filter_bandwidth(
            self._lib.pyhackrf_compute_baseband_filter_bw(sample_rate_hz),
        )
        self._device.pyhackrf_set_freq(center_hz)
        self._device.pyhackrf_set_amp_enable(bool(rf_amp_db))
        self._device.pyhackrf_set_lna_gain(lna_gain_db)
        self._device.pyhackrf_set_vga_gain(vga_gain_db)

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
        callback. Blocks until EOF (signalled via the tx-flush callback)
        or the kill switch fires.
        """
        assert self._device is not None
        loop = asyncio.get_running_loop()

        # Open file on a thread.
        file_handle = await loop.run_in_executor(None, lambda: iq_path.open("rb"))
        done_event = asyncio.Event()

        def tx_callback(
            device: Any,
            buffer: np.ndarray,  # dtype=int8, mutated in place
            buffer_length: int,
            _valid_length: int,
        ) -> int:
            if self._stop_event.is_set():
                return -1
            chunk = file_handle.read(buffer_length)
            if not chunk:
                return -1  # EOF; libhackrf stops
            n = len(chunk)
            buffer[:n] = np.frombuffer(chunk, dtype=np.int8)
            # If chunk was short, zero-fill the remainder so we don't emit
            # stale IQ from a previous buffer.
            if n < buffer_length:
                buffer[n:buffer_length] = 0
            return 0

        def tx_flush_callback(_device: Any, _success: int) -> None:
            loop.call_soon_threadsafe(done_event.set)

        try:
            await loop.run_in_executor(
                None,
                self._configure_tx,
                center_hz,
                sample_rate_hz,
                txvga_gain_db,
                rf_amp_db,
            )
            await loop.run_in_executor(None, self._device.set_tx_callback, tx_callback)
            await loop.run_in_executor(None, self._device.set_tx_flush_callback, tx_flush_callback)
            await loop.run_in_executor(None, self._device.pyhackrf_enable_tx_flush)
            await loop.run_in_executor(None, self._device.pyhackrf_start_tx)
            await done_event.wait()
        finally:
            file_handle.close()
            try:
                await loop.run_in_executor(None, self._device.pyhackrf_stop_tx)
            except Exception:  # noqa: BLE001 — best-effort stop
                pass

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
        self._device.pyhackrf_set_sample_rate(sample_rate_hz)
        self._device.pyhackrf_set_baseband_filter_bandwidth(
            self._lib.pyhackrf_compute_baseband_filter_bw(sample_rate_hz),
        )
        self._device.pyhackrf_set_freq(center_hz)
        self._device.pyhackrf_set_amp_enable(bool(rf_amp_db))
        self._device.pyhackrf_set_txvga_gain(txvga_gain_db)
