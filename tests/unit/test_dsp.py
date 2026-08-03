"""Unit tests for dsp.py — pure NumPy, zero hardware.

All signals are synthetic. Tests cover iq_to_complex64, fft_magnitude_db,
fft_freq_axis, estimate_noise_floor, and find_peaks.
"""

import numpy as np
import pytest

from hackrf_agent.hw.dsp import (
    Peak,
    estimate_noise_floor,
    fft_freq_axis,
    fft_magnitude_db,
    find_peaks,
    iq_to_complex64,
)

# ---------------------------------------------------------------------------
# Shared synthesizer — deterministic, seed-based
# ---------------------------------------------------------------------------


def synth_tone(
    freq_hz: float,
    sample_rate_hz: float,
    n: int,
    noise_rms: float = 0.01,
    amplitude: float = 0.5,
    seed_i: int = 42,
    seed_q: int = 43,
) -> np.ndarray:
    """Synthesize a complex64 tone with additive Gaussian noise."""
    t = np.arange(n) / sample_rate_hz
    signal = amplitude * np.exp(2j * np.pi * freq_hz * t)
    noise_i = np.random.default_rng(seed_i).normal(0, noise_rms, n)
    noise_q = np.random.default_rng(seed_q).normal(0, noise_rms, n)
    noise = noise_i + 1j * noise_q
    return (signal + noise).astype(np.complex64)


# ======================================================================
# iq_to_complex64
# ======================================================================


class TestIqToComplex64:
    def test_zero_bytes_produces_zero_array(self):
        """iq_to_complex64 of 8 zero-bytes returns 4 zero-complex samples."""
        result = iq_to_complex64(b"\x00\x00" * 4)
        assert len(result) == 4
        np.testing.assert_array_almost_equal(result, np.zeros(4, dtype=np.complex64))

    def test_odd_length_raises_valueerror(self):
        """Odd-length input raises ValueError."""
        with pytest.raises(ValueError, match="odd length"):
            iq_to_complex64(b"\x00")

    def test_fullscale_positive_and_negative(self):
        """int8 [127,0,-127,0] → [1+0j, -1+0j]."""
        arr = np.array([127, 0, -127, 0], dtype=np.int8)
        result = iq_to_complex64(arr)
        expected = np.array([1.0 + 0j, -1.0 + 0j], dtype=np.complex64)
        np.testing.assert_array_almost_equal(result, expected)

    def test_rejects_non_int8_array(self):
        """Passing a float32 array raises ValueError."""
        arr = np.array([1.0, 2.0], dtype=np.float32)
        with pytest.raises(ValueError, match="expected dtype int8"):
            iq_to_complex64(arr)

    def test_accepts_bytearray_and_memoryview(self):
        """iq_to_complex64 accepts bytearray and memoryview inputs."""
        raw = bytearray(b"\x00\x7f" * 10)  # 20 bytes → 10 samples
        result = iq_to_complex64(raw)
        assert len(result) == 10
        # memoryview
        result2 = iq_to_complex64(memoryview(raw))
        assert len(result2) == 10


# ======================================================================
# fft_magnitude_db
# ======================================================================


class TestFftMagnitudeDb:
    def test_tone_at_bin_center(self):
        """A tone at +100 kHz offset lands in the correct bin."""
        rate_hz = 2_000_000
        tone_offset = 100_000
        n = 65536
        iq = synth_tone(tone_offset, rate_hz, n, noise_rms=0.001)
        spec = fft_magnitude_db(iq, fft_size=4096)

        # The max bin should be near the tone offset.
        freqs = fft_freq_axis(0.0, rate_hz, 4096)
        max_bin = np.argmax(spec)
        actual_offset = abs(freqs[max_bin])
        bin_width = rate_hz / 4096
        assert abs(actual_offset - tone_offset) < bin_width * 2, (
            f"expected tone near {tone_offset} Hz, got {actual_offset} Hz"
        )

    def test_non_power_of_two_raises(self):
        """fft_size not a power of two raises ValueError."""
        iq = synth_tone(0, 2_000_000, 8192)
        with pytest.raises(ValueError, match="power of two"):
            fft_magnitude_db(iq, fft_size=1000)

    def test_too_short_input_raises(self):
        """Input shorter than fft_size raises ValueError."""
        iq = synth_tone(0, 2_000_000, 100)
        with pytest.raises(ValueError, match="need at least"):
            fft_magnitude_db(iq, fft_size=4096)

    def test_unknown_window_raises(self):
        """Unknown window name raises ValueError."""
        iq = synth_tone(0, 2_000_000, 8192)
        with pytest.raises(ValueError, match="unknown window"):
            fft_magnitude_db(iq, fft_size=4096, window="gaussian")

    def test_fft_size_edge_values(self):
        """fft_size 64 (minimum) and 65536 (maximum) are accepted."""
        iq_64 = synth_tone(0, 2_000_000, 128)
        spec = fft_magnitude_db(iq_64, fft_size=64)
        assert spec.shape == (64,)

        iq_max = synth_tone(0, 2_000_000, 131072)
        spec = fft_magnitude_db(iq_max, fft_size=65536)
        assert spec.shape == (65536,)

    def test_fft_size_below_minimum_raises(self):
        """fft_size below 64 raises ValueError."""
        iq = synth_tone(0, 2_000_000, 128)
        with pytest.raises(ValueError, match="power of two"):
            fft_magnitude_db(iq, fft_size=32)

    def test_blackman_harris_window_accepted(self):
        """The 'blackman-harris' window is accepted and runs."""
        iq = synth_tone(100_000, 2_000_000, 8192)
        spec = fft_magnitude_db(iq, fft_size=4096, window="blackman-harris")
        assert spec.shape == (4096,)

    def test_rect_window_accepted(self):
        """The 'rect' window is accepted and runs."""
        iq = synth_tone(100_000, 2_000_000, 8192)
        spec = fft_magnitude_db(iq, fft_size=4096, window="rect")
        assert spec.shape == (4096,)


# ======================================================================
# fft_freq_axis
# ======================================================================


class TestFftFreqAxis:
    def test_center_and_edges(self):
        """First element = center - rate/2, last = center + rate/2 - bin_hz."""
        center_hz = 433_920_000.0
        rate_hz = 2_000_000.0
        fft_size = 4096
        axis = fft_freq_axis(center_hz, rate_hz, fft_size)
        bin_hz = rate_hz / fft_size

        assert axis.shape == (fft_size,)
        assert axis[0] == pytest.approx(center_hz - rate_hz / 2)
        assert axis[-1] == pytest.approx(center_hz + rate_hz / 2 - bin_hz)
        # The center frequency should be near the middle.
        mid = fft_size // 2
        assert axis[mid] == pytest.approx(center_hz)


# ======================================================================
# estimate_noise_floor
# ======================================================================


class TestEstimateNoiseFloor:
    def test_pure_noise_floor(self):
        """On pure noise the estimator returns ~0 dB ±3 dB of true floor."""
        rng = np.random.default_rng(42)
        # Generate a flat spectrum around -80 dB
        noise_mag = 1e-4  # linear magnitude → -80 dB
        n_bins = 4096
        spectrum = 20.0 * np.log10(
            np.maximum(noise_mag * (1 + 0.1 * rng.normal(size=n_bins)), 1e-12)
        )
        floor = estimate_noise_floor(spectrum.astype(np.float32))
        # Should be roughly -80 dB ± 3 dB
        assert -83 < floor < -77, f"floor {floor} outside expected range"

    def test_empty_spectrum_raises(self):
        """Empty spectrum raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            estimate_noise_floor(np.array([], dtype=np.float32))

    def test_strong_tone_does_not_skew_floor(self):
        """Median-of-lower-half is robust against a few strong tones."""
        rng = np.random.default_rng(99)
        noise_mag = 1e-5  # -100 dB
        n_bins = 4096
        spectrum = 20.0 * np.log10(
            np.maximum(noise_mag * (1 + 0.05 * rng.normal(size=n_bins)), 1e-12)
        )
        # Insert a strong tone at bin 1000
        spectrum[1000] = -20.0  # much stronger
        floor = estimate_noise_floor(spectrum.astype(np.float32))
        # Floor should still be near -100, not pulled up by the tone.
        assert floor < -90, f"floor {floor} was pulled up by strong tone"


# ======================================================================
# find_peaks
# ======================================================================


class TestFindPeaks:
    def test_two_well_separated_tones(self):
        """Two tones at +200 kHz and -300 kHz produce exactly 2 peaks."""
        rate_hz = 2_000_000
        n = 65536
        t = np.arange(n) / rate_hz
        signal = (
            0.5 * np.exp(2j * np.pi * 200_000 * t)
            + 0.5 * np.exp(2j * np.pi * (-300_000) * t)
        )
        noise = 0.005 * (
            np.random.default_rng(0).normal(size=n)
            + 1j * np.random.default_rng(1).normal(size=n)
        )
        iq = (signal + noise).astype(np.complex64)

        spec = fft_magnitude_db(iq, fft_size=4096)
        freqs = fft_freq_axis(0.0, rate_hz, 4096)
        peaks = find_peaks(spec, freqs, top_n=5)

        assert len(peaks) >= 2, f"expected ≥2 peaks, got {len(peaks)}"
        peak_freqs = [p.freq_hz for p in peaks]
        bin_hz = rate_hz / 4096
        # Check we have peaks near +200k and -300k
        has_200k = any(abs(f - 200_000) < bin_hz * 3 for f in peak_freqs)
        has_300k = any(abs(f - (-300_000)) < bin_hz * 3 for f in peak_freqs)
        assert has_200k, f"no peak near +200 kHz in {peak_freqs}"
        assert has_300k, f"no peak near -300 kHz in {peak_freqs}"

    def test_top_n_limits_count(self):
        """find_peaks(top_n=1) on a two-tone signal returns only the stronger."""
        rate_hz = 2_000_000
        n = 65536
        t = np.arange(n) / rate_hz
        # One strong, one weak tone.
        signal = (
            0.8 * np.exp(2j * np.pi * 200_000 * t)
            + 0.2 * np.exp(2j * np.pi * (-300_000) * t)
        )
        noise = 0.005 * (
            np.random.default_rng(2).normal(size=n)
            + 1j * np.random.default_rng(3).normal(size=n)
        )
        iq = (signal + noise).astype(np.complex64)

        spec = fft_magnitude_db(iq, fft_size=4096)
        freqs = fft_freq_axis(0.0, rate_hz, 4096)
        peaks = find_peaks(spec, freqs, top_n=1)

        assert len(peaks) == 1
        # The stronger tone should be the one returned.
        bin_hz = rate_hz / 4096
        assert abs(peaks[0].freq_hz - 200_000) < bin_hz * 3

    def test_pure_noise_returns_empty(self):
        """find_peaks on pure noise returns an empty list (high prominence)."""
        rng = np.random.default_rng(7)
        noise = rng.normal(0, 0.002, 8192) + 1j * rng.normal(0, 0.002, 8192)
        iq = noise.astype(np.complex64)

        spec = fft_magnitude_db(iq, fft_size=4096)
        freqs = fft_freq_axis(0.0, 2_000_000, 4096)
        # Use a very high prominence threshold — pure noise should never
        # produce a local max 30 dB above the median-of-lower-half floor.
        peaks = find_peaks(spec, freqs, prominence_db=30.0, top_n=5)

        assert len(peaks) == 0, f"expected no peaks in pure noise, got {peaks}"

    def test_deduplicates_adjacent_bins(self):
        """With min_bin_gap=3, a tone produces well-separated peaks only."""
        rate_hz = 2_000_000
        n = 65536
        # Single strong tone
        iq = synth_tone(500_000, rate_hz, n, noise_rms=0.002, amplitude=0.9)
        spec = fft_magnitude_db(iq, fft_size=4096)
        freqs = fft_freq_axis(0.0, rate_hz, 4096)
        peaks = find_peaks(spec, freqs, top_n=5, min_bin_gap=3)

        # The strongest peak should be near 500 kHz.
        assert len(peaks) >= 1, f"expected at least one peak, got {len(peaks)}"
        bin_hz = rate_hz / 4096
        assert abs(peaks[0].freq_hz - 500_000) < bin_hz * 3
        # All peaks should be separated by at least min_bin_gap bins.
        for i in range(len(peaks)):
            for j in range(i + 1, len(peaks)):
                assert abs(peaks[i].bin_index - peaks[j].bin_index) >= 3, (
                    f"peaks {i} and {j} too close: "
                    f"bins {peaks[i].bin_index}, {peaks[j].bin_index}"
                )

    def test_mismatched_shape_raises(self):
        """spectrum and freq axis of different lengths raises ValueError."""
        spec = np.zeros(100, dtype=np.float32)
        freqs = np.zeros(200, dtype=np.float64)
        with pytest.raises(ValueError, match="same shape"):
            find_peaks(spec, freqs)

    def test_peak_dataclass_fields(self):
        """Returned Peak objects have all required fields."""
        rate_hz = 2_000_000
        iq = synth_tone(300_000, rate_hz, 65536, noise_rms=0.002)
        spec = fft_magnitude_db(iq, fft_size=4096)
        freqs = fft_freq_axis(0.0, rate_hz, 4096)
        peaks = find_peaks(spec, freqs, top_n=1)

        assert len(peaks) == 1
        p = peaks[0]
        assert isinstance(p, Peak)
        assert isinstance(p.freq_hz, float)
        assert isinstance(p.power_dbfs, float)
        assert isinstance(p.prominence_db, float)
        assert isinstance(p.bin_index, int)
        assert 0 <= p.bin_index < 4096
        assert p.prominence_db >= 6.0  # default prominence threshold
