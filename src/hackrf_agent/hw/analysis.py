"""Offline IQ analysis primitives — pure NumPy, no hardware access.

Zero I/O beyond the caller-supplied ``iq_path``. Zero ``pyhackrf`` import.
Every function operates on already-captured IQ data on disk.

Public surface:

- ``load_iq_file`` — read a HackRF-native ``.cs8`` interleaved-int8 file
  into ``complex64`` samples with a bounded max size.
- ``ModulationCandidate`` — one candidate result from
  ``classify_modulation``.
- ``classify_modulation`` — moment-based heuristic classifier.
- ``estimate_symbol_rate`` — magnitude-squared autocorrelation.
- ``spectrogram_summary`` — compact per-slice bin-max summary (never
  the full FFT matrix — that would flood the LLM context).
- ``SlicedSymbols`` — bit-level output shared by the decoders.
- ``slice_ook`` — OOK envelope → bit array at symbol rate.
- ``decode_manchester`` / ``decode_pwm`` / ``decode_ppm`` /
  ``decode_nrz`` — line-code decoders on top of the slicer.

Nothing here uses ``pyhackrf``. This module runs in every CI job because
it needs only NumPy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from hackrf_agent.hw.dsp import iq_to_complex64

# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------

MAX_IQ_FILE_BYTES: int = 1_073_741_824  # 1 GiB cap on offline IQ files
_MAX_SPECTROGRAM_SLICES: int = 512
_MIN_ENV_SAMPLES: int = 256


# ---------------------------------------------------------------------------
# File loader
# ---------------------------------------------------------------------------


def load_iq_file(path: Path) -> npt.NDArray[np.complex64]:
    """Read a HackRF ``.cs8`` file into complex64 samples.

    HackRF's ``hackrf_transfer`` writes signed int8 interleaved I/Q with no
    header. This is the same convention the ``capture_iq`` handler uses
    for on-disk captures. Files above ``MAX_IQ_FILE_BYTES`` are rejected
    to bound memory use — the caller must decimate at capture time or
    split the file.

    Raises:
        FileNotFoundError: path does not exist or is not a file.
        ValueError: file too large, empty, or has an odd byte count.
    """
    if not path.is_file():
        raise FileNotFoundError(f"iq file not found: {path}")
    size = path.stat().st_size
    if size == 0:
        raise ValueError(f"iq file is empty: {path}")
    if size > MAX_IQ_FILE_BYTES:
        raise ValueError(
            f"iq file too large ({size} bytes > {MAX_IQ_FILE_BYTES} cap): {path}"
        )
    raw = path.read_bytes()
    return iq_to_complex64(raw)


# ---------------------------------------------------------------------------
# Modulation classifier
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModulationCandidate:
    """One candidate returned by ``classify_modulation``."""

    family: str
    confidence: float  # 0.0..1.0 heuristic — not calibrated
    note: str


def classify_modulation(
    iq: npt.NDArray[np.complex64],
) -> list[ModulationCandidate]:
    """Return a ranked list of candidate modulation families.

    Heuristics used:

    - **Envelope variance / mean**. Near-zero → constant-envelope
      (FM/FSK/PSK). High → amplitude-carrying (AM/OOK/ASK/QAM).
    - **Envelope bimodality**. Two-cluster envelope with a wide gap →
      OOK. Even distribution → QAM/AM.
    - **Instantaneous-frequency bimodality**. Two-cluster inst.freq. →
      2FSK. Continuous inst.freq. → FM voice / GFSK / MSK / GMSK.
    - **Phase variance**. Wraps rapidly around ±π → PSK-family.

    The results are heuristic, not ML-trained. A candidate's confidence
    ∈ [0,1] captures how well the moment-based tests agreed; call this a
    starting point for the LLM to reason from, never a definitive
    classification. Callers should surface at least the top three.
    """
    if iq.size < _MIN_ENV_SAMPLES:
        return [
            ModulationCandidate(
                family="unknown",
                confidence=0.0,
                note=f"too few samples ({iq.size} < {_MIN_ENV_SAMPLES})",
            )
        ]

    envelope = np.abs(iq).astype(np.float64)
    env_mean = float(np.mean(envelope))
    env_std = float(np.std(envelope))
    env_cv = env_std / env_mean if env_mean > 1e-9 else 0.0

    # OOK detection: bimodality in the envelope. Cluster the envelope into
    # low/high halves relative to the midpoint and check if both halves
    # are well-populated with a clear gap.
    midpoint = (envelope.min() + envelope.max()) / 2.0
    lo_mask = envelope < midpoint
    hi_mask = envelope >= midpoint
    lo_frac = float(np.mean(lo_mask))
    hi_frac = float(np.mean(hi_mask))
    if hi_mask.sum() > 0 and lo_mask.sum() > 0:
        hi_mean = float(np.mean(envelope[hi_mask]))
        lo_mean = float(np.mean(envelope[lo_mask]))
        gap_ratio = (hi_mean - lo_mean) / (hi_mean + lo_mean + 1e-9)
    else:
        gap_ratio = 0.0

    # Instantaneous frequency: unwrap the phase and diff it.
    phase = np.unwrap(np.angle(iq.astype(np.complex128)))
    inst_freq = np.diff(phase)
    if inst_freq.size == 0:
        inst_freq = np.zeros(1)
    inst_freq_std = float(np.std(inst_freq))
    inst_freq_mean = float(np.mean(inst_freq))

    # 2FSK detection: inst.freq. concentrates near two discrete values.
    # Use histogram bimodality: build 32 bins and check that the top two
    # bins account for a large share of the mass.
    hist, _ = np.histogram(inst_freq, bins=32)
    top2 = np.sort(hist)[-2:]
    total = int(hist.sum())
    top2_share = float(top2.sum() / total) if total > 0 else 0.0

    candidates: list[ModulationCandidate] = []

    # OOK — needs a real amplitude gap and both halves populated.
    if 0.1 < lo_frac < 0.9 and gap_ratio > 0.5 and env_cv > 0.4:
        candidates.append(
            ModulationCandidate(
                family="OOK",
                confidence=min(1.0, gap_ratio),
                note=(
                    f"envelope splits into two clusters "
                    f"(low_frac={lo_frac:.2f}, gap_ratio={gap_ratio:.2f}, "
                    f"cv={env_cv:.2f})"
                ),
            )
        )

    # 2FSK — bimodal instantaneous frequency + roughly constant envelope.
    if top2_share > 0.5 and env_cv < 0.3:
        candidates.append(
            ModulationCandidate(
                family="2FSK",
                confidence=min(1.0, top2_share),
                note=(
                    f"instantaneous frequency clusters at 2 lobes "
                    f"(top2_share={top2_share:.2f}, envelope cv={env_cv:.2f})"
                ),
            )
        )

    # Constant-envelope carrier / FM / PSK.
    if env_cv < 0.15:
        if inst_freq_std < 1e-4:
            family = "unmodulated carrier (constant envelope, constant phase)"
        else:
            family = "FM/PSK (constant envelope)"
        candidates.append(
            ModulationCandidate(
                family=family,
                confidence=min(1.0, 1.0 - env_cv * 2.0),
                note=(
                    f"envelope is near-flat (cv={env_cv:.3f}); "
                    f"inst_freq_std={inst_freq_std:.3e}"
                ),
            )
        )

    # AM / QAM: variable envelope, no bimodality, phase varies smoothly.
    if env_cv > 0.15 and gap_ratio < 0.4 and inst_freq_std > 1e-6:
        candidates.append(
            ModulationCandidate(
                family="AM/QAM (amplitude-carrying)",
                confidence=min(1.0, env_cv),
                note=(
                    f"envelope varies smoothly (cv={env_cv:.2f}); "
                    f"no clear on/off gap"
                ),
            )
        )

    # Fallback — nothing matched a heuristic.
    if not candidates:
        candidates.append(
            ModulationCandidate(
                family="unknown",
                confidence=0.0,
                note=(
                    f"no heuristic matched (env_cv={env_cv:.2f}, "
                    f"gap_ratio={gap_ratio:.2f}, top2_share={top2_share:.2f})"
                ),
            )
        )

    # Sort by confidence, descending.
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates


# ---------------------------------------------------------------------------
# Symbol-rate estimator
# ---------------------------------------------------------------------------


def estimate_symbol_rate(
    iq: npt.NDArray[np.complex64],
    sample_rate_hz: int,
    min_rate_hz: float = 100.0,
    max_rate_hz: float | None = None,
) -> dict[str, float | str]:
    """Estimate the symbol rate of an IQ capture from envelope edges.

    Method: threshold the envelope to detect ON/OFF transitions, then
    take the greatest-common-divisor (approximated via a robust min of
    inter-edge intervals, filtered to the plausible range) as the
    symbol-period estimate. Works well for OOK/ASK with mostly random
    bit patterns. For FSK or continuous-envelope modulations, the
    caller must either preprocess (matched filter, threshold on
    instantaneous frequency) or hint the rate directly.

    Args:
        iq: complex64 samples.
        sample_rate_hz: capture sample rate.
        min_rate_hz: lower bound for symbol rate search (default 100 Hz).
        max_rate_hz: upper bound (default: sample_rate_hz / 8).

    Returns:
        ``{"symbol_rate_hz", "confidence", "method", "lag_samples",
        "num_edges"}``. ``symbol_rate_hz == 0.0`` and ``confidence ==
        0.0`` when no reliable estimate is available.
    """
    if iq.size < 1024:
        return {
            "symbol_rate_hz": 0.0,
            "confidence": 0.0,
            "method": "edge-interval",
            "lag_samples": 0,
            "num_edges": 0,
            "note": f"too few samples ({iq.size} < 1024)",
        }
    if max_rate_hz is None:
        max_rate_hz = sample_rate_hz / 8.0
    if min_rate_hz >= max_rate_hz:
        raise ValueError(
            f"min_rate_hz ({min_rate_hz}) must be < max_rate_hz ({max_rate_hz})"
        )

    env = np.abs(iq).astype(np.float64)
    threshold = (env.min() + env.max()) / 2.0
    binary = (env > threshold).astype(np.int8)
    # Edges are non-zero diffs of the binary trace.
    edge_positions = np.flatnonzero(np.diff(binary) != 0)
    num_edges = int(edge_positions.size)
    if num_edges < 4:
        return {
            "symbol_rate_hz": 0.0,
            "confidence": 0.0,
            "method": "edge-interval",
            "lag_samples": 0,
            "num_edges": num_edges,
            "note": "not enough transitions to estimate rate",
        }

    intervals = np.diff(edge_positions)
    lag_min = max(1, int(sample_rate_hz / max_rate_hz))
    lag_max = int(sample_rate_hz / min_rate_hz)
    intervals = intervals[(intervals >= lag_min) & (intervals <= lag_max)]
    if intervals.size < 4:
        return {
            "symbol_rate_hz": 0.0,
            "confidence": 0.0,
            "method": "edge-interval",
            "lag_samples": 0,
            "num_edges": num_edges,
            "note": (
                f"no inter-edge intervals inside search range "
                f"[{lag_min}, {lag_max}]"
            ),
        }

    # The smallest common interval is the symbol period. Use the 5th
    # percentile of the interval histogram to reject outliers/jitter
    # while still landing on the shortest recurring gap.
    p5 = float(np.percentile(intervals, 5))
    # Cluster intervals within +/- 25% of p5 to build the estimate.
    near = intervals[
        (intervals >= 0.75 * p5) & (intervals <= 1.25 * p5)
    ]
    if near.size < 2:
        peak_lag = int(round(p5))
    else:
        peak_lag = int(round(float(np.median(near))))
    if peak_lag <= 0:
        peak_lag = int(round(p5))
    symbol_rate = float(sample_rate_hz) / peak_lag

    # Confidence: fraction of intervals that are integer multiples of
    # the estimated period (within ±20%). High for clean signals with
    # random bits; low for pathological captures.
    quotients = intervals / peak_lag
    close_to_int = np.abs(quotients - np.round(quotients)) < 0.20
    confidence = float(np.mean(close_to_int))

    return {
        "symbol_rate_hz": symbol_rate,
        "confidence": confidence,
        "method": "edge-interval",
        "lag_samples": peak_lag,
        "num_edges": num_edges,
    }


# ---------------------------------------------------------------------------
# Spectrogram summary
# ---------------------------------------------------------------------------


def spectrogram_summary(
    iq: npt.NDArray[np.complex64],
    sample_rate_hz: int,
    fft_size: int = 1024,
    overlap: float = 0.5,
    max_slices: int = _MAX_SPECTROGRAM_SLICES,
) -> dict[str, object]:
    """Compute a compact spectrogram summary.

    For each FFT slice: the frequency (relative to center = 0) of the peak
    bin and its magnitude in dBFS. Never returns the full FFT matrix —
    that would flood the LLM's context with numbers it cannot interpret.

    Args:
        iq: complex64 samples.
        sample_rate_hz: capture sample rate.
        fft_size: bins per slice. Power of two in [64, 65536].
        overlap: fraction of overlap between slices, in [0, 0.9].
        max_slices: cap on the number of returned slices. If the capture
            would yield more, we uniformly subsample.

    Returns:
        ``{"num_slices", "step_samples", "peak_freqs_hz", "peak_dbfs",
        "peak_bin_indices"}`` — plus ``truncated`` if we dropped slices
        to fit the cap.
    """
    if fft_size & (fft_size - 1) != 0 or not (64 <= fft_size <= 65536):
        raise ValueError(
            f"fft_size must be a power of two in [64, 65536], got {fft_size}"
        )
    if not 0.0 <= overlap < 0.95:
        raise ValueError(f"overlap must be in [0.0, 0.95), got {overlap}")
    if iq.size < fft_size:
        raise ValueError(
            f"need at least {fft_size} samples, got {iq.size}"
        )

    step = max(1, int(fft_size * (1.0 - overlap)))
    n_full = (iq.size - fft_size) // step + 1

    # Downsample if needed.
    if n_full > max_slices:
        indices = np.linspace(0, n_full - 1, max_slices, dtype=int)
        truncated = True
    else:
        indices = np.arange(n_full)
        truncated = False

    window = np.hanning(fft_size).astype(np.float32)
    freq_axis = np.fft.fftshift(
        np.fft.fftfreq(fft_size, d=1.0 / sample_rate_hz)
    )

    peak_freqs: list[float] = []
    peak_powers: list[float] = []
    peak_bins: list[int] = []
    for slice_index in indices:
        start = int(slice_index * step)
        segment = iq[start : start + fft_size] * window
        spec = np.fft.fftshift(np.fft.fft(segment))
        mag2 = (spec.real ** 2 + spec.imag ** 2).astype(np.float64)
        peak_bin = int(np.argmax(mag2))
        peak_bins.append(peak_bin)
        peak_freqs.append(float(freq_axis[peak_bin]))
        # dBFS relative to fft_size normalized full-scale.
        norm = float(mag2[peak_bin]) / (fft_size * fft_size)
        peak_dbfs = 10.0 * float(np.log10(norm + 1e-24))
        peak_powers.append(peak_dbfs)

    return {
        "num_slices": len(indices),
        "step_samples": step,
        "fft_size": fft_size,
        "sample_rate_hz": sample_rate_hz,
        "peak_freqs_hz": peak_freqs,
        "peak_dbfs": peak_powers,
        "peak_bin_indices": peak_bins,
        "truncated": truncated,
    }


# ---------------------------------------------------------------------------
# Line-code decoders — shared slicer + per-code state machines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SlicedSymbols:
    """Result of the OOK-envelope slicer.

    ``bits`` is a numpy array of 0/1 values, one per symbol period at the
    caller's specified symbol rate. ``samples_per_symbol`` is the number
    of input samples that were collapsed into each output bit.
    """

    bits: npt.NDArray[np.uint8]
    samples_per_symbol: int
    threshold: float


def slice_ook(
    iq: npt.NDArray[np.complex64],
    sample_rate_hz: int,
    symbol_rate_hz: float,
) -> SlicedSymbols:
    """Threshold the envelope and downsample to one bit per symbol.

    Uses the midpoint between min and max envelope samples as the
    threshold — robust for clean OOK bursts. For lower-SNR bursts callers
    should preprocess (e.g., matched filter) before calling.

    Raises ``ValueError`` if the symbol rate would produce less than one
    sample per symbol, or fewer than 8 symbols total.
    """
    if symbol_rate_hz <= 0:
        raise ValueError(f"symbol_rate_hz must be > 0, got {symbol_rate_hz}")
    sps = int(round(sample_rate_hz / symbol_rate_hz))
    if sps < 2:
        raise ValueError(
            f"symbol rate too high: {sps} samples/symbol at fs={sample_rate_hz}"
        )
    env = np.abs(iq).astype(np.float32)
    if env.size < 8 * sps:
        raise ValueError(
            f"not enough samples: {env.size} < 8 symbols x {sps} samples"
        )

    threshold = float(env.min() + env.max()) / 2.0
    n_symbols = env.size // sps
    trimmed = env[: n_symbols * sps].reshape(n_symbols, sps)
    # Symbol decision: majority of samples above threshold.
    above = (trimmed > threshold).sum(axis=1)
    bits = (above > (sps // 2)).astype(np.uint8)
    return SlicedSymbols(bits=bits, samples_per_symbol=sps, threshold=threshold)


def decode_manchester(
    iq: npt.NDArray[np.complex64],
    sample_rate_hz: int,
    symbol_rate_hz: float,
    polarity: str = "ieee",
) -> dict[str, object]:
    """Manchester decoder.

    IEEE 802.3 polarity: 01 → 1, 10 → 0. G.E. Thomas polarity: 01 → 0,
    10 → 1. Manchester encodes each bit as two half-symbols at ``2 x
    symbol_rate_hz``, so we slice at that double rate then merge pairs.

    Returns:
        ``{"bits", "num_bits", "polarity", "samples_per_halfsymbol",
        "unmerged_halfsymbols", "invalid_pairs"}``. ``invalid_pairs`` is
        the count of half-symbol pairs where both halves matched
        (``00`` or ``11``) — a symbol-timing error.
    """
    if polarity not in ("ieee", "thomas"):
        raise ValueError(f"polarity must be 'ieee' or 'thomas', got {polarity}")

    sliced = slice_ook(iq, sample_rate_hz, 2.0 * symbol_rate_hz)
    halves = sliced.bits
    n_pairs = halves.size // 2
    trimmed = halves[: n_pairs * 2].reshape(n_pairs, 2)

    bits = np.zeros(n_pairs, dtype=np.uint8)
    invalid = 0
    for i in range(n_pairs):
        a, b = int(trimmed[i, 0]), int(trimmed[i, 1])
        if a == b:
            invalid += 1
            bits[i] = 0
            continue
        if polarity == "ieee":
            bits[i] = 1 if (a == 0 and b == 1) else 0
        else:  # thomas
            bits[i] = 0 if (a == 0 and b == 1) else 1

    return {
        "bits": bits.tolist(),
        "num_bits": int(n_pairs),
        "polarity": polarity,
        "samples_per_halfsymbol": sliced.samples_per_symbol,
        "invalid_pairs": int(invalid),
        "threshold": sliced.threshold,
    }


def decode_pwm(
    iq: npt.NDArray[np.complex64],
    sample_rate_hz: int,
    short_us: float,
    long_us: float,
) -> dict[str, object]:
    """PWM decoder — measures ON-pulse widths against ``short_us`` and
    ``long_us``.

    A "0" is a short-then-long or a short pulse; a "1" is a long pulse.
    Multiple PWM conventions exist; this decoder assumes the OOK-simple
    convention where each bit is a single ON pulse of ``short_us`` (0)
    or ``long_us`` (1), separated by a gap. Callers with a different
    convention should slice the envelope themselves and interpret pulse
    widths using this function's ``pulse_widths_us`` output.

    Returns:
        ``{"bits", "num_bits", "pulse_widths_us", "invalid_pulses"}``.
    """
    if short_us <= 0 or long_us <= 0:
        raise ValueError(
            f"short_us and long_us must be > 0, got {short_us}, {long_us}"
        )
    if short_us >= long_us:
        raise ValueError(
            f"short_us ({short_us}) must be < long_us ({long_us})"
        )
    us_per_sample = 1_000_000.0 / sample_rate_hz
    env = np.abs(iq).astype(np.float32)
    threshold = float(env.min() + env.max()) / 2.0
    on = env > threshold

    # Find runs of ON samples.
    pulse_widths_us: list[float] = []
    i = 0
    while i < on.size:
        if not on[i]:
            i += 1
            continue
        start = i
        while i < on.size and on[i]:
            i += 1
        width_us = (i - start) * us_per_sample
        pulse_widths_us.append(width_us)

    midpoint_us = (short_us + long_us) / 2.0
    tolerance = (long_us - short_us) * 0.35
    bits: list[int] = []
    invalid = 0
    for w in pulse_widths_us:
        if abs(w - short_us) <= tolerance:
            bits.append(0)
        elif abs(w - long_us) <= tolerance:
            bits.append(1)
        elif w < midpoint_us:
            bits.append(0)
            invalid += 1
        else:
            bits.append(1)
            invalid += 1

    return {
        "bits": bits,
        "num_bits": len(bits),
        "pulse_widths_us": pulse_widths_us,
        "short_us": short_us,
        "long_us": long_us,
        "invalid_pulses": invalid,
        "threshold": threshold,
    }


def decode_ppm(
    iq: npt.NDArray[np.complex64],
    sample_rate_hz: int,
    pulse_us: float,
) -> dict[str, object]:
    """PPM decoder — a "1" is a pulse in the first half of the symbol
    period; a "0" is a pulse in the second half.

    Symbol period is ``2 * pulse_us``. We find each ON pulse, compute its
    center in symbol-period units, and slice on whether the center is
    below or above the midpoint of its symbol slot.

    Returns:
        ``{"bits", "num_bits", "pulse_centers_us", "pulse_us"}``.
    """
    if pulse_us <= 0:
        raise ValueError(f"pulse_us must be > 0, got {pulse_us}")
    us_per_sample = 1_000_000.0 / sample_rate_hz
    env = np.abs(iq).astype(np.float32)
    threshold = float(env.min() + env.max()) / 2.0
    on = env > threshold
    symbol_period_us = 2.0 * pulse_us

    centers_us: list[float] = []
    i = 0
    while i < on.size:
        if not on[i]:
            i += 1
            continue
        start = i
        while i < on.size and on[i]:
            i += 1
        center = (start + i) / 2.0 * us_per_sample
        centers_us.append(center)

    bits: list[int] = []
    for c in centers_us:
        # Fold into the symbol period.
        pos_in_symbol = c % symbol_period_us
        bits.append(1 if pos_in_symbol < pulse_us else 0)

    return {
        "bits": bits,
        "num_bits": len(bits),
        "pulse_centers_us": centers_us,
        "pulse_us": pulse_us,
        "symbol_period_us": symbol_period_us,
        "threshold": threshold,
    }


def decode_nrz(
    iq: npt.NDArray[np.complex64],
    sample_rate_hz: int,
    symbol_rate_hz: float,
    inverted: bool = False,
) -> dict[str, object]:
    """NRZ line-code decoder.

    NRZ: high level for 1, low level for 0 (or inverted). Just slices the
    OOK envelope at the symbol rate. Companion NRZI variant available via
    the ``differential`` flag — set ``inverted=True`` to invert polarity.

    Returns:
        ``{"bits", "num_bits", "samples_per_symbol", "inverted"}``.
    """
    sliced = slice_ook(iq, sample_rate_hz, symbol_rate_hz)
    bits = sliced.bits
    if inverted:
        bits = 1 - bits
    return {
        "bits": bits.astype(int).tolist(),
        "num_bits": int(bits.size),
        "samples_per_symbol": sliced.samples_per_symbol,
        "inverted": inverted,
        "threshold": sliced.threshold,
    }


def decode_nrzi(
    iq: npt.NDArray[np.complex64],
    sample_rate_hz: int,
    symbol_rate_hz: float,
) -> dict[str, object]:
    """NRZI decoder — a transition means 1, no transition means 0.

    Returns:
        ``{"bits", "num_bits", "samples_per_symbol"}``.
    """
    sliced = slice_ook(iq, sample_rate_hz, symbol_rate_hz)
    levels = sliced.bits
    if levels.size == 0:
        return {"bits": [], "num_bits": 0, "samples_per_symbol": sliced.samples_per_symbol}
    diffs = np.diff(levels.astype(np.int8))
    bits = (diffs != 0).astype(np.uint8)
    return {
        "bits": bits.tolist(),
        "num_bits": int(bits.size),
        "samples_per_symbol": sliced.samples_per_symbol,
        "threshold": sliced.threshold,
    }


# ---------------------------------------------------------------------------
# POCSAG decoder
# ---------------------------------------------------------------------------

_POCSAG_SYNC: int = 0x7CD215D8
_POCSAG_IDLE: int = 0x7A89C197
_POCSAG_BCH_GEN: int = 0b11101101001  # 0x769, x^10+x^9+x^8+x^6+x^5+x^3+1
_POCSAG_BAUDS: tuple[int, ...] = (512, 1200, 2400)


def _pocsag_bch_syndrome(codeword_31: int) -> int:
    """Compute BCH(31,21) syndrome. Returns 0 for a valid 31-bit codeword.

    ``codeword_31`` is the 31 bits of data+parity (excluding the trailing
    even-parity bit).
    """
    cw = codeword_31 & 0x7FFFFFFF  # 31 bits
    for i in range(30, 9, -1):
        if cw & (1 << i):
            cw ^= _POCSAG_BCH_GEN << (i - 10)
    return cw & 0x3FF  # 10-bit remainder


def _pocsag_even_parity(codeword_32: int) -> int:
    """Return 1 iff the 32-bit codeword has odd number of 1-bits (i.e.
    even-parity check fails)."""
    x = codeword_32
    x ^= x >> 16
    x ^= x >> 8
    x ^= x >> 4
    x ^= x >> 2
    x ^= x >> 1
    return x & 1


def _pocsag_2fsk_demod(
    iq: npt.NDArray[np.complex64],
    sample_rate_hz: int,
    baud: int,
) -> npt.NDArray[np.uint8]:
    """Demodulate a 2FSK POCSAG stream to a bit array at ``baud``.

    Uses the instantaneous-frequency method: unwrap phase, take diff,
    threshold at the median. High frequency = 0 (mark), low frequency = 1
    (space) per POCSAG convention. Returns one bit per symbol period.
    """
    phase = np.unwrap(np.angle(iq.astype(np.complex128)))
    inst_freq = np.diff(phase)
    if inst_freq.size == 0:
        return np.zeros(0, dtype=np.uint8)
    # np.diff drops one sample; repeat the last value so slicing at
    # ``iq.size`` samples produces the same number of symbols we expect
    # from the raw sample count.
    inst_freq = np.concatenate([inst_freq, inst_freq[-1:]])
    threshold = float(np.median(inst_freq))
    binary = (inst_freq > threshold).astype(np.int8)  # 1 = high freq

    sps = int(round(sample_rate_hz / baud))
    if sps < 2:
        return np.zeros(0, dtype=np.uint8)
    n_symbols = binary.size // sps
    if n_symbols == 0:
        return np.zeros(0, dtype=np.uint8)
    trimmed = binary[: n_symbols * sps].reshape(n_symbols, sps)
    # Majority vote per symbol.
    above = trimmed.sum(axis=1)
    bits = (above > (sps // 2)).astype(np.uint8)
    # POCSAG: high frequency = 0 (mark), low frequency = 1 (space) —
    # invert the "high-freq = 1" convention.
    return 1 - bits


def _bits_to_uint32_be(bits: npt.NDArray[np.uint8]) -> int:
    """Pack a 32-bit big-endian bit array (MSB first) into an int."""
    v = 0
    for b in bits:
        v = (v << 1) | int(b)
    return v


def _pocsag_find_sync(bits: npt.NDArray[np.uint8]) -> list[int]:
    """Return start indices of every occurrence of the 32-bit sync word."""
    if bits.size < 32:
        return []
    sync_bits = np.array(
        [(_POCSAG_SYNC >> (31 - i)) & 1 for i in range(32)], dtype=np.uint8
    )
    hits: list[int] = []
    # Sliding window; small enough for direct comparison.
    end = bits.size - 32 + 1
    for i in range(end):
        if np.array_equal(bits[i : i + 32], sync_bits):
            hits.append(i)
    return hits


def _pocsag_parse_codeword(
    cw32: int, frame_slot: int
) -> dict[str, object]:
    """Parse one 32-bit POCSAG codeword.

    Returns:
        A dict with ``flag`` ("address" | "message" | "idle"), plus the
        role-specific fields. Also always includes ``bch_ok`` and
        ``parity_ok``.
    """
    bch_ok = _pocsag_bch_syndrome(cw32 >> 1) == 0
    parity_ok = _pocsag_even_parity(cw32) == 0
    if cw32 == _POCSAG_IDLE:
        return {
            "flag": "idle",
            "raw_hex": f"0x{cw32:08X}",
            "bch_ok": bch_ok,
            "parity_ok": parity_ok,
        }
    is_message = (cw32 >> 31) & 1
    if is_message == 0:
        # Address codeword.
        address_upper18 = (cw32 >> 13) & 0x3FFFF
        function = (cw32 >> 11) & 0x3
        # RIC = address_upper18 << 3 | frame_slot
        ric = (address_upper18 << 3) | (frame_slot & 0x7)
        return {
            "flag": "address",
            "ric": int(ric),
            "function": int(function),
            "raw_hex": f"0x{cw32:08X}",
            "bch_ok": bch_ok,
            "parity_ok": parity_ok,
        }
    # Message codeword.
    message_bits = (cw32 >> 11) & 0xFFFFF  # 20 bits
    return {
        "flag": "message",
        "message_bits": int(message_bits),
        "raw_hex": f"0x{cw32:08X}",
        "bch_ok": bch_ok,
        "parity_ok": parity_ok,
    }


def _pocsag_decode_numeric(bit_stream: str) -> str:
    """Interpret an accumulated message bit stream as POCSAG numeric BCD.

    Groups the bit stream into 4-bit nibbles (LSB first per POCSAG spec
    — bit-reversed relative to the transmission order within each
    nibble). The 16 codes map to ``0-9`` and the special chars
    ``[spare]U [ ]spare``.
    """
    codes = "0123456789*U -]"
    out: list[str] = []
    # POCSAG numeric: 4 bits per digit, sent LSB-first (least-significant
    # bit transmitted first). The received-order MSB-first stream is
    # bit-reversed inside each nibble.
    for i in range(0, len(bit_stream) - 3, 4):
        nib = bit_stream[i : i + 4]
        # Reverse to interpret MSB-first as if it were LSB-first.
        val = int(nib[::-1], 2)
        out.append(codes[val] if val < len(codes) else "?")
    return "".join(out)


def _pocsag_decode_alpha(bit_stream: str) -> str:
    """Interpret an accumulated message bit stream as POCSAG 7-bit ASCII.

    Groups the bit stream into 7-bit chars, LSB first per POCSAG spec.
    """
    out: list[str] = []
    for i in range(0, len(bit_stream) - 6, 7):
        septet = bit_stream[i : i + 7]
        val = int(septet[::-1], 2)  # LSB-first → reverse to reconstruct
        if 32 <= val < 127:
            out.append(chr(val))
        else:
            out.append(f"[0x{val:02X}]")
    return "".join(out)


def decode_pocsag(
    iq: npt.NDArray[np.complex64],
    sample_rate_hz: int,
    baud: int = 1200,
) -> dict[str, object]:
    """POCSAG 512/1200/2400 paging decoder.

    2FSK-demodulates the input, searches for the 32-bit sync word
    ``0x7CD215D8``, parses each 8-frame batch after every sync into
    codewords, and assembles messages (address codeword + subsequent
    message codewords, up to the next address or idle).

    For each message, both numeric-BCD and 7-bit-ASCII interpretations
    are returned — the caller picks the one the payload looks like.
    Function bits (0-3) hint at which encoding the pager used:
    function 0 = numeric; 3 = alphanumeric; 1/2 = tone/voice-alert.

    Args:
        iq: complex64 samples.
        sample_rate_hz: capture sample rate.
        baud: 512, 1200, or 2400. Must be present in ``_POCSAG_BAUDS``.

    Returns:
        ``{"baud", "sync_offsets", "num_codewords", "messages",
        "invalid_codewords"}``. ``messages`` is a list of dicts
        containing ``ric``, ``function``, ``numeric``, ``alpha``,
        ``codeword_count``.
    """
    if baud not in _POCSAG_BAUDS:
        raise ValueError(f"baud must be one of {_POCSAG_BAUDS}, got {baud}")

    bits = _pocsag_2fsk_demod(iq, sample_rate_hz, baud)
    if bits.size < 32:
        return {
            "baud": baud,
            "sync_offsets": [],
            "num_codewords": 0,
            "messages": [],
            "invalid_codewords": 0,
            "note": "not enough symbols after 2FSK demod",
        }

    # Try both polarities — the "which tone is 0/1" convention varies by
    # transmitter. Pick the polarity that yields more sync-word hits.
    inv = 1 - bits
    hits_pos = _pocsag_find_sync(bits)
    hits_neg = _pocsag_find_sync(inv)
    if len(hits_neg) > len(hits_pos):
        bits = inv
        sync_offsets = hits_neg
    else:
        sync_offsets = hits_pos

    messages: list[dict[str, object]] = []
    invalid_codewords = 0
    num_codewords = 0

    for sync_off in sync_offsets:
        # A batch has 16 codewords (8 frames * 2) = 512 bits after the sync.
        cw_start = sync_off + 32
        current_addr: dict[str, object] | None = None
        current_bits: list[str] = []
        for cw_idx in range(16):
            start = cw_start + cw_idx * 32
            end = start + 32
            if end > bits.size:
                break
            cw = _bits_to_uint32_be(bits[start:end])
            num_codewords += 1
            frame_slot = cw_idx // 2  # 8 frames of 2 codewords each
            parsed = _pocsag_parse_codeword(cw, frame_slot)
            if not parsed.get("bch_ok"):
                invalid_codewords += 1
            flag = parsed["flag"]
            if flag == "idle":
                # Close out any pending message.
                if current_addr is not None:
                    messages.append(
                        _pocsag_finalize_message(current_addr, current_bits)
                    )
                    current_addr = None
                    current_bits = []
                continue
            if flag == "address":
                if current_addr is not None:
                    messages.append(
                        _pocsag_finalize_message(current_addr, current_bits)
                    )
                current_addr = parsed
                current_bits = []
                continue
            # Message codeword — accumulate 20 payload bits (MSB first).
            payload = parsed["message_bits"]  # 20-bit int
            for b in range(19, -1, -1):
                current_bits.append("1" if (payload >> b) & 1 else "0")
        # End of batch — flush any pending message.
        if current_addr is not None:
            messages.append(
                _pocsag_finalize_message(current_addr, current_bits)
            )

    return {
        "baud": baud,
        "sync_offsets": sync_offsets,
        "num_codewords": num_codewords,
        "invalid_codewords": invalid_codewords,
        "messages": messages,
    }


def _pocsag_finalize_message(
    addr: dict[str, object], bits: list[str]
) -> dict[str, object]:
    """Turn accumulated bits into numeric + alpha payload strings."""
    bit_stream = "".join(bits)
    return {
        "ric": addr["ric"],
        "function": addr["function"],
        "numeric": _pocsag_decode_numeric(bit_stream) if bit_stream else "",
        "alpha": _pocsag_decode_alpha(bit_stream) if bit_stream else "",
        "message_bit_count": len(bit_stream),
    }


# ---------------------------------------------------------------------------
# ADS-B / Mode S decoder
# ---------------------------------------------------------------------------

# Mode S CRC-24 generator polynomial: x^24 + x^23 + x^22 + x^21 + x^20 +
# x^19 + x^18 + x^17 + x^16 + x^15 + x^14 + x^13 + x^12 + x^10 + x^3 + 1
# = 0x1FFF409 (25-bit representation) → 0xFFF409 for the 24-bit trailing part.
_MODES_CRC_POLY: int = 0xFFF409
_MODES_LONG_MSG_BITS: int = 112
_MODES_SHORT_MSG_BITS: int = 56
# Preamble pattern at 1 Mbps: pulses at t=0, 1.0, 3.5, 4.5 μs, each 0.5 μs
# wide, in an 8 μs window. Encoded as a 16-chip pattern at 2 chips/μs.
# The chip pattern is:
#   1 0 1 0 0 0 0 1 0 1 0 0 0 0 0 0
_MODES_PREAMBLE_CHIPS: list[int] = [
    1, 0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0
]


def _modes_crc24(bits: npt.NDArray[np.uint8]) -> int:
    """CRC-24 over a Mode S message.

    Iterates MSB-first. For a valid DF17 message the CRC over the full
    112 bits (including the trailing 24-bit checksum) is zero. For DF11
    it equals the ICAO24 (address/parity overlay).
    """
    reg = 0
    for b in bits:
        reg = ((reg << 1) | int(b)) & 0xFFFFFFFF
        if reg & (1 << 24):
            reg ^= (1 << 24) | _MODES_CRC_POLY
    return reg & 0xFFFFFF


def _modes_ppm_slice(
    envelope: npt.NDArray[np.float32],
    fs: int,
    start_idx: int,
    n_bits: int,
) -> npt.NDArray[np.uint8]:
    """Slice ``n_bits`` PPM chips from the envelope starting at
    ``start_idx``.

    Each bit is 1 μs = ``fs / 1e6`` samples. Bit "1" = pulse in the
    first half; bit "0" = pulse in the second half.
    """
    sps_per_us = fs / 1_000_000
    if sps_per_us < 2:
        # Below Nyquist for the 0.5 μs chip.
        return np.zeros(0, dtype=np.uint8)
    samples_per_bit = int(round(sps_per_us))
    half = samples_per_bit // 2
    end = start_idx + n_bits * samples_per_bit
    if end > envelope.size:
        return np.zeros(0, dtype=np.uint8)
    bits = np.zeros(n_bits, dtype=np.uint8)
    for i in range(n_bits):
        base = start_idx + i * samples_per_bit
        first_half = float(np.sum(envelope[base : base + half]))
        second_half = float(np.sum(envelope[base + half : base + samples_per_bit]))
        bits[i] = 1 if first_half > second_half else 0
    return bits


def _modes_find_preambles(
    envelope: npt.NDArray[np.float32],
    fs: int,
    max_frames: int = 4096,
) -> list[int]:
    """Return sample indices where the Mode S preamble likely begins.

    Uses correlation of the envelope against the expected 8 μs preamble
    chip pattern, then thresholds at the top few percent of correlation
    values. This is deliberately loose: a real dump1090 uses a much more
    sophisticated preamble detector, but for CTF-scale clean captures
    a peaked correlation is enough.
    """
    sps_per_us = fs / 1_000_000
    if sps_per_us < 2:
        return []
    samples_per_chip = int(round(sps_per_us / 2))
    template = np.repeat(np.array(_MODES_PREAMBLE_CHIPS, dtype=np.float32), samples_per_chip)
    template = template - template.mean()
    env_c = envelope.astype(np.float32) - float(np.mean(envelope))
    if env_c.size < template.size:
        return []
    corr = np.convolve(env_c, template[::-1], mode="valid")
    if corr.size == 0:
        return []
    threshold = float(np.percentile(corr, 99.5))
    if threshold <= 0:
        return []
    # Non-max suppression: keep peaks separated by at least one full
    # (preamble + long-frame) span so we don't return overlapping hits.
    min_gap = int(sps_per_us * (8 + _MODES_LONG_MSG_BITS))
    hits: list[int] = []
    last = -min_gap
    for i in np.flatnonzero(corr > threshold):
        if i - last >= min_gap:
            hits.append(int(i))
            last = int(i)
            if len(hits) >= max_frames:
                break
    return hits


def decode_ads_b(
    iq: npt.NDArray[np.complex64],
    sample_rate_hz: int,
    max_frames: int = 64,
) -> dict[str, object]:
    """Mode S / ADS-B decoder for captured IQ at 1090 MHz.

    Requires ``sample_rate_hz >= 2_000_000`` for the 0.5 μs chip
    resolution. Decodes 112-bit long frames (DF17 = extended squitter =
    ADS-B). For DF17 the CRC over the 112-bit message is zero when
    valid; for DF11 the CRC equals the ICAO24 address (parity-address
    overlay). We report the DF field and the ICAO24 field
    unconditionally so callers can inspect even CRC-failed frames.

    Args:
        iq: complex64 samples (Mode S is always at 1090 MHz).
        sample_rate_hz: capture rate; must be >= 2 MHz.
        max_frames: cap on decoded frames.

    Returns:
        ``{"sample_rate_hz", "num_preambles", "frames"}``. Each frame is
        ``{"start_sample", "df", "icao24_hex", "raw_hex", "crc_residual",
        "crc_ok"}``.
    """
    if sample_rate_hz < 2_000_000:
        raise ValueError(
            f"ADS-B requires sample_rate_hz >= 2000000, got {sample_rate_hz}"
        )
    envelope = np.abs(iq).astype(np.float32)
    preambles = _modes_find_preambles(envelope, sample_rate_hz, max_frames=max_frames * 4)
    frames: list[dict[str, object]] = []

    sps_per_us = sample_rate_hz / 1_000_000
    samples_per_us = int(round(sps_per_us))
    preamble_samples = 8 * samples_per_us

    for pre_idx in preambles:
        if len(frames) >= max_frames:
            break
        payload_idx = pre_idx + preamble_samples
        bits = _modes_ppm_slice(
            envelope, sample_rate_hz, payload_idx, _MODES_LONG_MSG_BITS
        )
        if bits.size < _MODES_LONG_MSG_BITS:
            continue
        df = int((bits[0] << 4) | (bits[1] << 3) | (bits[2] << 2) | (bits[3] << 1) | bits[4])
        crc_residual = _modes_crc24(bits)
        crc_ok = crc_residual == 0
        # Message byte layout (14 bytes = 112 bits, MSB first).
        raw_bytes = bytearray(14)
        for i in range(14):
            byte_val = 0
            for j in range(8):
                byte_val = (byte_val << 1) | int(bits[i * 8 + j])
            raw_bytes[i] = byte_val
        raw_hex = raw_bytes.hex().upper()
        icao24 = 0
        for i in range(8, 32):
            icao24 = (icao24 << 1) | int(bits[i])
        frames.append(
            {
                "start_sample": int(payload_idx),
                "df": df,
                "icao24_hex": f"{icao24:06X}",
                "raw_hex": raw_hex,
                "crc_residual": int(crc_residual),
                "crc_ok": bool(crc_ok),
            }
        )

    return {
        "sample_rate_hz": sample_rate_hz,
        "num_preambles": len(preambles),
        "frames": frames,
    }
