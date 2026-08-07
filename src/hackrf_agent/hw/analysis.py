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
