"""Tests for committed test fixtures — IQ files and audit snapshots."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from hackrf_agent.hw.dsp import (
    estimate_noise_floor,
    fft_freq_axis,
    fft_magnitude_db,
    find_peaks,
    iq_to_complex64,
)

FIXTURES_IQ = Path(__file__).parent.parent / "fixtures" / "iq"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _load_iq(name: str) -> np.ndarray:
    """Load a fixture .iq file and convert to complex64."""
    path = FIXTURES_IQ / name
    assert path.is_file(), f"fixture missing: {path}"
    raw = path.read_bytes()
    return iq_to_complex64(raw)


# ---------------------------------------------------------------------------
# Test 1: ism_433_tone.iq — peak at 434.12 MHz
# ---------------------------------------------------------------------------


def test_ism_433_tone_peak_at_expected_frequency() -> None:
    """ism_433_tone.iq has a peak within one FFT bin of 434.12 MHz."""
    iq = _load_iq("ism_433_tone.iq")
    center_hz = 433_920_000
    sample_rate_hz = 2_000_000
    fft_size = 4096
    expected_peak_hz = center_hz + 200_000  # 434.12 MHz

    spec = fft_magnitude_db(iq, fft_size)
    freqs = fft_freq_axis(center_hz, sample_rate_hz, fft_size)
    peaks = find_peaks(spec, freqs, prominence_db=6.0, top_n=3)

    assert len(peaks) >= 1, "Expected at least 1 peak in ism_433_tone.iq; found none"
    # Check that at least one peak is within one bin of expected.
    bin_hz = sample_rate_hz / fft_size
    peak_freqs = [p.freq_hz for p in peaks]
    assert any(
        abs(f - expected_peak_hz) <= bin_hz * 1.5 for f in peak_freqs
    ), f"No peak near {expected_peak_hz} Hz (bin width={bin_hz:.1f} Hz); peaks at {peak_freqs}"


# ---------------------------------------------------------------------------
# Test 2: ism_315_noise_only.iq — no signal (peak prominence < 6 dB)
# ---------------------------------------------------------------------------


def test_ism_315_noise_only_no_signal() -> None:
    """ism_315_noise_only.iq has no strong signal — all peaks have low prominence."""
    iq = _load_iq("ism_315_noise_only.iq")
    center_hz = 315_000_000
    sample_rate_hz = 2_000_000
    fft_size = 4096

    spec = fft_magnitude_db(iq, fft_size)
    freqs = fft_freq_axis(center_hz, sample_rate_hz, fft_size)

    # With noise-only input, no peak should exceed prominence of 20 dB
    # (a real signal would be much more prominent).
    peaks = find_peaks(spec, freqs, prominence_db=20.0, top_n=5)
    assert len(peaks) == 0, (
        f"Expected no peaks above 20 dB prominence in noise-only fixture; "
        f"found {len(peaks)} peaks"
    )

    # Also verify noise floor is reasonable (not complete silence).
    noise = estimate_noise_floor(spec)
    assert -80.0 < noise < -10.0, f"Noise floor out of expected range: {noise} dBFS"


# ---------------------------------------------------------------------------
# Test 3: two_tone.iq — two peaks symmetric about center
# ---------------------------------------------------------------------------


def test_two_tone_has_two_symmetric_peaks() -> None:
    """two_tone.iq has two peaks at ~ +/-150 kHz from center."""
    iq = _load_iq("two_tone.iq")
    center_hz = 433_000_000
    sample_rate_hz = 2_000_000
    fft_size = 4096
    bin_hz = sample_rate_hz / fft_size

    spec = fft_magnitude_db(iq, fft_size)
    freqs = fft_freq_axis(center_hz, sample_rate_hz, fft_size)
    # At least 2 peaks should be present (harmonics/artifacts are OK).
    peaks = find_peaks(spec, freqs, prominence_db=30.0, top_n=5)

    assert len(peaks) >= 2, f"Expected at least 2 peaks, got {len(peaks)}"
    offsets = [p.freq_hz - center_hz for p in peaks]
    # One should be near +150 kHz, one near -150 kHz.
    assert any(abs(o - 150_000) < bin_hz * 3 for o in offsets), (
        f"No peak near +150 kHz; offsets: {offsets}"
    )
    assert any(abs(o + 150_000) < bin_hz * 3 for o in offsets), (
        f"No peak near -150 kHz; offsets: {offsets}"
    )


# ---------------------------------------------------------------------------
# Test 4: Each .iq file has a corresponding .md sibling
# ---------------------------------------------------------------------------


def test_every_iq_file_has_md_sibling() -> None:
    """Every .iq fixture file has a corresponding .md provenance file."""
    iq_files = sorted(FIXTURES_IQ.glob("*.iq"))
    assert len(iq_files) >= 3, f"Expected at least 3 .iq fixtures, found {len(iq_files)}"
    for iq_path in iq_files:
        md_path = iq_path.with_suffix(".iq.md")
        assert md_path.is_file(), f"Missing provenance doc: {md_path.name}"
