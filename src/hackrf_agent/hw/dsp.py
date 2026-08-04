"""Pure NumPy DSP primitives for HackRF IQ data.

Zero I/O, zero hardware, no ``pyhackrf`` import. This module runs in
every CI job because it needs nothing beyond NumPy.

Public surface
--------------
- ``iq_to_complex64`` — int8 interleaved IQ → complex64 samples.
- ``fft_magnitude_db`` — complex64 samples → dBFS magnitude spectrum.
- ``fft_freq_axis`` — matching frequency axis (fftshifted).
- ``estimate_noise_floor`` — robust noise-floor estimator.
- ``find_peaks`` — peak detector with prominence filtering.
- ``Peak`` — frozen dataclass for one detected peak.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt

# ---------------------------------------------------------------------------
# Windows — map name → factory(n: int) -> np.ndarray[float32]
# ---------------------------------------------------------------------------


def _blackman_harris(n: int) -> npt.NDArray[np.float32]:
    """A Blackman-Harris 4-term window (minimum side-lobe)."""
    a0, a1, a2, a3 = 0.35875, 0.48829, 0.14128, 0.01168
    k = np.arange(n, dtype=np.float64)
    result: npt.NDArray[np.float32] = (
        a0
        - a1 * np.cos(2.0 * np.pi * k / (n - 1))
        + a2 * np.cos(4.0 * np.pi * k / (n - 1))
        - a3 * np.cos(6.0 * np.pi * k / (n - 1))
    ).astype(np.float32)
    return result


_WINDOWS: Final[dict[str, Callable[[int], npt.NDArray[np.float32]]]] = {
    "hann": lambda n: np.hanning(n).astype(np.float32),
    "blackman-harris": _blackman_harris,
    "rect": lambda n: np.ones(n, dtype=np.float32),
}

# ---------------------------------------------------------------------------
# Peak dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Peak:
    """One detected peak in a magnitude spectrum."""

    freq_hz: float
    power_dbfs: float
    prominence_db: float
    bin_index: int


# ---------------------------------------------------------------------------
# IQ conversion
# ---------------------------------------------------------------------------


def iq_to_complex64(raw: bytes | npt.NDArray[np.int8]) -> npt.NDArray[np.complex64]:
    """Convert libhackrf's int8 interleaved I/Q buffer to complex64 samples.

    libhackrf produces signed 8-bit values in [-128, 127]. We rescale to
    the [-1.0, 1.0] range so downstream DSP produces meaningful dBFS.
    Division by 127 places 0 dBFS at true fullscale (libhackrf's producers
    saturate at 127, not 128).

    Accepts either raw bytes (from disk or the USB callback) or a numpy
    int8 array. Returns a complex64 array of length ``len(raw) // 2``.

    Raises ``ValueError`` if the input length is odd (unpaired I sample).
    """
    if isinstance(raw, (bytes, bytearray, memoryview)):
        arr: npt.NDArray[np.int8] = np.frombuffer(raw, dtype=np.int8)
    else:
        if raw.dtype != np.int8:
            raise ValueError(f"expected dtype int8, got {raw.dtype}")
        arr = raw
    if arr.size % 2 != 0:
        raise ValueError("IQ buffer has odd length — I/Q pair mismatch")
    scaled = arr.astype(np.float32) / 127.0
    return (scaled[0::2] + 1j * scaled[1::2]).astype(np.complex64)


# ---------------------------------------------------------------------------
# FFT magnitude spectrum
# ---------------------------------------------------------------------------


def fft_magnitude_db(
    iq: npt.NDArray[np.complex64],
    fft_size: int,
    window: str = "hann",
) -> npt.NDArray[np.float32]:
    """Compute a magnitude spectrum in dBFS.

    Args:
        iq: complex64 samples, at least ``fft_size`` long. Extra samples
            are discarded (single-shot spectrum, not averaged).
        fft_size: must be a power of two, ≥ 64, ≤ 65536.
        window: one of ``_WINDOWS`` keys.

    Returns:
        float32 array of length ``fft_size``, ordered by
        ``np.fft.fftshift`` (negative freqs first, then positive).
        Callers pair with a frequency axis from ``fft_freq_axis()``.
    """
    if fft_size & (fft_size - 1) != 0 or not (64 <= fft_size <= 65536):
        raise ValueError(f"fft_size must be a power of two in [64, 65536], got {fft_size}")
    if iq.size < fft_size:
        raise ValueError(f"need at least {fft_size} samples, got {iq.size}")
    if window not in _WINDOWS:
        raise ValueError(f"unknown window {window!r}; choices: {sorted(_WINDOWS)}")

    w = _WINDOWS[window](fft_size).astype(np.float32)
    # Normalize window so 0 dBFS corresponds to a full-scale sinusoid.
    w /= w.mean()
    frame = iq[:fft_size] * w
    spec = np.fft.fftshift(np.fft.fft(frame))
    mag = np.abs(spec).astype(np.float32) / fft_size
    # Guard against log(0) — clip to a numerical floor.
    result: npt.NDArray[np.float32] = (20.0 * np.log10(np.maximum(mag, 1e-12))).astype(np.float32)
    return result


def fft_freq_axis(
    center_hz: float, sample_rate_hz: float, fft_size: int
) -> npt.NDArray[np.float64]:
    """Frequency axis matching ``fft_magnitude_db``'s bin order (fftshifted).

    Returns a float64 array of length ``fft_size``.
    """
    bin_hz = sample_rate_hz / fft_size
    return center_hz + (np.arange(fft_size, dtype=np.float64) - fft_size // 2) * bin_hz


# ---------------------------------------------------------------------------
# Noise floor estimation
# ---------------------------------------------------------------------------


def estimate_noise_floor(spectrum_db: npt.NDArray[np.float32]) -> float:
    """Median-of-lower-half estimator.

    Robust against a handful of strong tones dominating the spectrum. Not
    as fancy as MAD or Welch's method, but good enough for peak-picking
    context. Returns a float dBFS value.
    """
    if spectrum_db.size == 0:
        raise ValueError("empty spectrum")
    sorted_spec = np.sort(spectrum_db)
    return float(np.median(sorted_spec[: spectrum_db.size // 2]))


# ---------------------------------------------------------------------------
# Peak detection
# ---------------------------------------------------------------------------


def find_peaks(
    spectrum_db: npt.NDArray[np.float32],
    freqs_hz: npt.NDArray[np.float64],
    prominence_db: float = 6.0,
    top_n: int = 5,
    min_bin_gap: int = 3,
) -> list[Peak]:
    """Return the top-N peaks, ordered by descending power.

    A peak is a local maximum whose height exceeds the local floor by at
    least ``prominence_db``. Peaks within ``min_bin_gap`` bins of a
    stronger peak are suppressed (single-tone deduplication).

    Args:
        spectrum_db: fftshifted magnitude spectrum (from ``fft_magnitude_db``).
        freqs_hz: matching frequency axis (from ``fft_freq_axis``). Must be
            the same length as ``spectrum_db``.
        prominence_db: minimum peak-to-floor height to count.
        top_n: maximum number of peaks returned.
        min_bin_gap: minimum bin separation between reported peaks.
    """
    if spectrum_db.shape != freqs_hz.shape:
        raise ValueError("spectrum and frequency axis must have the same shape")

    floor = estimate_noise_floor(spectrum_db)

    # Local-max mask: strictly greater than both neighbours.
    n = spectrum_db.size
    is_local_max = np.zeros(n, dtype=bool)
    is_local_max[1:-1] = (spectrum_db[1:-1] > spectrum_db[:-2]) & (
        spectrum_db[1:-1] > spectrum_db[2:]
    )

    candidate_idx = np.where(is_local_max & (spectrum_db - floor >= prominence_db))[0]

    # Sort candidates by descending power.
    candidate_idx = candidate_idx[np.argsort(-spectrum_db[candidate_idx])]

    kept: list[int] = []
    for idx in candidate_idx:
        if all(abs(idx - k) >= min_bin_gap for k in kept):
            kept.append(int(idx))
            if len(kept) >= top_n:
                break

    return [
        Peak(
            freq_hz=float(freqs_hz[i]),
            power_dbfs=float(spectrum_db[i]),
            prominence_db=float(spectrum_db[i] - floor),
            bin_index=i,
        )
        for i in kept
    ]
