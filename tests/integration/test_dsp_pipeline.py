"""Integration test — synthetic signal through the full DSP pipeline.

No hardware, no pyhackrf. Proves that iq_to_complex64 → fft_magnitude_db
→ fft_freq_axis → find_peaks preserves a known tone through int8
quantization.

This test is the day-1 canary. If it starts failing, someone changed one
of the DSP primitives in a way that broke the pipeline shape.
"""

import numpy as np

from hackrf_agent.hw.dsp import (
    fft_freq_axis,
    fft_magnitude_db,
    find_peaks,
    iq_to_complex64,
)


def test_synthetic_tone_recovery_end_to_end():
    """A synthetic 433.925 MHz tone survives int8 quantization,
    FFT, and peak-detection."""
    center_hz = 433_920_000
    rate_hz = 2_000_000
    tone_offset_hz = 5_000  # tone at 433.925 MHz
    n = 65536

    t = np.arange(n) / rate_hz
    signal = 0.5 * np.exp(2j * np.pi * tone_offset_hz * t)
    noise = 0.01 * (
        np.random.default_rng(0).normal(size=n) + 1j * np.random.default_rng(1).normal(size=n)
    )
    iq_complex = (signal + noise).astype(np.complex64)

    # Quantize to int8 the way libhackrf would produce it.
    quant = np.empty(2 * n, dtype=np.int8)
    quant[0::2] = np.clip(np.round(iq_complex.real * 127), -127, 127).astype(np.int8)
    quant[1::2] = np.clip(np.round(iq_complex.imag * 127), -127, 127).astype(np.int8)
    raw = quant.tobytes()

    # Pipeline.
    iq = iq_to_complex64(raw)
    spec = fft_magnitude_db(iq, fft_size=4096)
    freqs = fft_freq_axis(center_hz, rate_hz, 4096)
    peaks = find_peaks(spec, freqs, top_n=3)

    assert peaks, "expected at least one peak"
    top = peaks[0]
    bin_hz = rate_hz / 4096
    assert abs(top.freq_hz - (center_hz + tone_offset_hz)) < bin_hz * 2, (
        f"peak at {top.freq_hz} Hz, expected near {center_hz + tone_offset_hz} Hz "
        f"(bin width {bin_hz:.1f} Hz)"
    )


def test_stronger_tone_at_different_offset():
    """A tone at -200 kHz offset also survives the full pipeline."""
    center_hz = 915_000_000
    rate_hz = 4_000_000
    tone_offset_hz = -200_000  # tone at 914.8 MHz
    n = 65536

    t = np.arange(n) / rate_hz
    signal = 0.7 * np.exp(2j * np.pi * tone_offset_hz * t)
    noise = 0.005 * (
        np.random.default_rng(10).normal(size=n) + 1j * np.random.default_rng(11).normal(size=n)
    )
    iq_complex = (signal + noise).astype(np.complex64)

    quant = np.empty(2 * n, dtype=np.int8)
    quant[0::2] = np.clip(np.round(iq_complex.real * 127), -127, 127).astype(np.int8)
    quant[1::2] = np.clip(np.round(iq_complex.imag * 127), -127, 127).astype(np.int8)
    raw = quant.tobytes()

    iq = iq_to_complex64(raw)
    spec = fft_magnitude_db(iq, fft_size=8192)
    freqs = fft_freq_axis(center_hz, rate_hz, 8192)
    peaks = find_peaks(spec, freqs, top_n=3)

    assert peaks, "expected at least one peak"
    top = peaks[0]
    bin_hz = rate_hz / 8192
    expected = center_hz + tone_offset_hz
    assert abs(top.freq_hz - expected) < bin_hz * 2, (
        f"peak at {top.freq_hz} Hz, expected near {expected} Hz"
    )
