"""Tests for hackrf_agent.hw.analysis (Phase 3 analysis primitives)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hackrf_agent.hw.analysis import (
    MAX_IQ_FILE_BYTES,
    classify_modulation,
    decode_manchester,
    decode_nrz,
    decode_nrzi,
    decode_ppm,
    decode_pwm,
    estimate_symbol_rate,
    load_iq_file,
    slice_ook,
    spectrogram_summary,
)


# ---------------------------------------------------------------------------
# Fixtures — synthetic signals
# ---------------------------------------------------------------------------


def _make_ook(
    bits: list[int],
    fs: int,
    symbol_rate: int,
    noise_std: float = 0.02,
    seed: int = 0,
) -> np.ndarray:
    """Build an OOK complex-baseband signal at ``symbol_rate`` bps."""
    sps = fs // symbol_rate
    env = np.repeat(np.array(bits, dtype=np.float32), sps) * 0.9 + 0.05
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, noise_std, env.size).astype(np.float32)
    return (env + noise).astype(np.complex64)


def _make_fm_carrier(
    freq_offset: int,
    duration_s: float,
    fs: int,
) -> np.ndarray:
    """Constant-envelope complex sinusoid — the simplest FM/PSK signal."""
    n = int(duration_s * fs)
    t = np.arange(n) / fs
    return np.exp(1j * 2 * np.pi * freq_offset * t).astype(np.complex64)


# ---------------------------------------------------------------------------
# load_iq_file
# ---------------------------------------------------------------------------


class TestLoadIqFile:
    def test_reads_cs8_file(self, tmp_path: Path) -> None:
        # Write 100 samples worth of int8 IQ
        raw = np.array([64, 32, -64, -32] * 50, dtype=np.int8)
        p = tmp_path / "test.cs8"
        p.write_bytes(raw.tobytes())
        iq = load_iq_file(p)
        assert iq.dtype == np.complex64
        assert iq.size == 100

    def test_rejects_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_iq_file(tmp_path / "nope.cs8")

    def test_rejects_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.cs8"
        p.write_bytes(b"")
        with pytest.raises(ValueError, match="empty"):
            load_iq_file(p)

    def test_rejects_odd_byte_count(self, tmp_path: Path) -> None:
        p = tmp_path / "odd.cs8"
        p.write_bytes(b"\x00\x01\x02")  # 3 bytes — not paired
        with pytest.raises(ValueError, match="odd"):
            load_iq_file(p)

    def test_size_cap(self) -> None:
        assert MAX_IQ_FILE_BYTES == 1_073_741_824


# ---------------------------------------------------------------------------
# classify_modulation
# ---------------------------------------------------------------------------


class TestClassifyModulation:
    def test_ook_top_candidate(self) -> None:
        bits = [1, 0, 1, 1, 0, 0, 1, 0] * 50
        iq = _make_ook(bits, fs=1_000_000, symbol_rate=1000)
        cands = classify_modulation(iq)
        assert cands[0].family == "OOK"
        assert cands[0].confidence > 0.5

    def test_constant_envelope_flagged(self) -> None:
        iq = _make_fm_carrier(freq_offset=10_000, duration_s=0.1, fs=1_000_000)
        cands = classify_modulation(iq)
        families = [c.family.lower() for c in cands]
        # A pure carrier is constant-envelope and constant-phase in the
        # complex-baseband frame — the classifier should surface that.
        assert any("constant envelope" in f for f in families)

    def test_too_few_samples(self) -> None:
        iq = np.zeros(10, dtype=np.complex64)
        cands = classify_modulation(iq)
        assert cands[0].family == "unknown"


# ---------------------------------------------------------------------------
# estimate_symbol_rate
# ---------------------------------------------------------------------------


class TestEstimateSymbolRate:
    @pytest.mark.parametrize("symbol_rate", [500, 1000, 2000, 4000])
    def test_recovers_ook_rate(self, symbol_rate: int) -> None:
        fs = 1_000_000
        rng = np.random.default_rng(42)
        n_bits = 500
        bits = rng.integers(0, 2, n_bits).tolist()
        iq = _make_ook(bits, fs=fs, symbol_rate=symbol_rate)
        r = estimate_symbol_rate(iq, sample_rate_hz=fs)
        # Within 5% of the true rate.
        assert abs(r["symbol_rate_hz"] - symbol_rate) / symbol_rate < 0.05
        assert r["confidence"] > 0.5

    def test_returns_zero_on_short(self) -> None:
        iq = np.zeros(500, dtype=np.complex64)
        r = estimate_symbol_rate(iq, sample_rate_hz=1_000_000)
        assert r["symbol_rate_hz"] == 0.0
        assert r["confidence"] == 0.0

    def test_rejects_bad_range(self) -> None:
        iq = np.ones(2000, dtype=np.complex64)
        with pytest.raises(ValueError, match="min_rate_hz"):
            estimate_symbol_rate(
                iq, sample_rate_hz=1_000_000, min_rate_hz=1000, max_rate_hz=100
            )


# ---------------------------------------------------------------------------
# spectrogram_summary
# ---------------------------------------------------------------------------


class TestSpectrogramSummary:
    def test_returns_expected_shape(self) -> None:
        iq = _make_fm_carrier(freq_offset=100_000, duration_s=0.05, fs=1_000_000)
        summary = spectrogram_summary(
            iq, sample_rate_hz=1_000_000, fft_size=1024, overlap=0.5
        )
        assert summary["num_slices"] > 0
        assert len(summary["peak_freqs_hz"]) == summary["num_slices"]
        assert len(summary["peak_dbfs"]) == summary["num_slices"]

    def test_peak_freq_near_carrier(self) -> None:
        iq = _make_fm_carrier(freq_offset=100_000, duration_s=0.05, fs=1_000_000)
        summary = spectrogram_summary(
            iq, sample_rate_hz=1_000_000, fft_size=1024, overlap=0.5
        )
        peaks = summary["peak_freqs_hz"]
        # Every slice's peak should be within one bin width of 100 kHz.
        bin_width = 1_000_000 / 1024
        for p in peaks:
            assert abs(p - 100_000) < 2 * bin_width

    def test_truncated_flag(self) -> None:
        iq = _make_fm_carrier(freq_offset=0, duration_s=1.0, fs=1_000_000)
        summary = spectrogram_summary(
            iq, sample_rate_hz=1_000_000, fft_size=256, overlap=0.5, max_slices=16
        )
        assert summary["num_slices"] == 16
        assert summary["truncated"] is True

    def test_rejects_non_pow2_fft(self) -> None:
        iq = _make_fm_carrier(0, 0.05, 1_000_000)
        with pytest.raises(ValueError, match="power of two"):
            spectrogram_summary(iq, 1_000_000, fft_size=1000)

    def test_rejects_too_few_samples(self) -> None:
        iq = np.zeros(100, dtype=np.complex64)
        with pytest.raises(ValueError, match="samples"):
            spectrogram_summary(iq, 1_000_000, fft_size=1024)


# ---------------------------------------------------------------------------
# slice_ook
# ---------------------------------------------------------------------------


class TestSliceOok:
    def test_recovers_clean_bits(self) -> None:
        bits = [1, 0, 1, 1, 0, 0, 1, 0] * 30
        iq = _make_ook(bits, fs=1_000_000, symbol_rate=1000)
        sliced = slice_ook(iq, sample_rate_hz=1_000_000, symbol_rate_hz=1000)
        # First N slots should match (allowing for edge effects at start/end).
        assert sliced.bits[:len(bits) - 2].tolist() == bits[:len(bits) - 2]

    def test_rejects_too_high_rate(self) -> None:
        iq = _make_ook([1, 0] * 100, fs=1_000_000, symbol_rate=1000)
        with pytest.raises(ValueError, match="samples/symbol"):
            slice_ook(iq, sample_rate_hz=1_000_000, symbol_rate_hz=2_000_000)

    def test_rejects_short(self) -> None:
        iq = np.ones(100, dtype=np.complex64)
        with pytest.raises(ValueError, match="not enough samples"):
            slice_ook(iq, sample_rate_hz=1_000_000, symbol_rate_hz=1000)


# ---------------------------------------------------------------------------
# decode_manchester
# ---------------------------------------------------------------------------


class TestDecodeManchester:
    def test_ieee_polarity(self) -> None:
        # Bits: 1 0 1 1 0. IEEE encoding: 01 10 01 01 10.
        bits = [1, 0, 1, 1, 0] * 10
        pairs: list[int] = []
        for b in bits:
            pairs.extend([0, 1] if b == 1 else [1, 0])
        fs = 1_000_000
        symbol_rate = 1000  # bits per second
        sps = fs // (symbol_rate * 2)  # each Manchester half-symbol
        env = np.repeat(np.array(pairs, dtype=np.float32), sps) * 0.9 + 0.05
        iq = env.astype(np.complex64)
        result = decode_manchester(
            iq, sample_rate_hz=fs, symbol_rate_hz=symbol_rate, polarity="ieee"
        )
        # Match the first N bits (skip end effects).
        recovered = result["bits"][: len(bits) - 1]
        assert recovered == bits[: len(bits) - 1]
        assert result["invalid_pairs"] == 0

    def test_thomas_polarity_inverts(self) -> None:
        bits = [1, 0, 1, 0] * 10
        pairs: list[int] = []
        for b in bits:
            pairs.extend([0, 1] if b == 1 else [1, 0])
        fs = 1_000_000
        symbol_rate = 1000
        sps = fs // (symbol_rate * 2)
        env = np.repeat(np.array(pairs, dtype=np.float32), sps) * 0.9 + 0.05
        iq = env.astype(np.complex64)
        result = decode_manchester(iq, fs, symbol_rate, polarity="thomas")
        # With Thomas polarity, our IEEE-encoded bits invert.
        expected = [1 - b for b in bits]
        assert result["bits"][: len(expected) - 1] == expected[: len(expected) - 1]

    def test_bad_polarity(self) -> None:
        iq = np.ones(10_000, dtype=np.complex64)
        with pytest.raises(ValueError, match="polarity"):
            decode_manchester(iq, 1_000_000, 1000, polarity="rocket")


# ---------------------------------------------------------------------------
# decode_pwm
# ---------------------------------------------------------------------------


class TestDecodePwm:
    def test_recovers_bits(self) -> None:
        # Construct a signal with alternating short and long ON pulses.
        # short_us=400, long_us=800. Gap between pulses = 400us.
        fs = 1_000_000
        us_per_sample = 1_000_000 / fs
        short_samples = int(400 / us_per_sample)
        long_samples = int(800 / us_per_sample)
        gap_samples = int(400 / us_per_sample)
        bits_ref = [0, 1, 0, 1, 1, 0, 1, 0]
        env_parts = []
        for b in bits_ref:
            width = long_samples if b == 1 else short_samples
            env_parts.append(np.ones(width, dtype=np.float32))
            env_parts.append(np.zeros(gap_samples, dtype=np.float32))
        env = np.concatenate(env_parts)
        iq = env.astype(np.complex64)
        result = decode_pwm(iq, fs, short_us=400, long_us=800)
        assert result["bits"] == bits_ref
        assert result["invalid_pulses"] == 0

    def test_rejects_bad_widths(self) -> None:
        iq = np.ones(1000, dtype=np.complex64)
        with pytest.raises(ValueError, match="must be <"):
            decode_pwm(iq, 1_000_000, short_us=500, long_us=300)

    def test_rejects_zero_width(self) -> None:
        iq = np.ones(1000, dtype=np.complex64)
        with pytest.raises(ValueError, match="must be > 0"):
            decode_pwm(iq, 1_000_000, short_us=0, long_us=500)


# ---------------------------------------------------------------------------
# decode_ppm
# ---------------------------------------------------------------------------


class TestDecodePpm:
    def test_recovers_bits(self) -> None:
        # Real PPM: a narrow pulse inside a wider half-slot. If the pulse
        # were the full width of a half-slot, adjacent bits' pulses would
        # touch and merge. 100us pulses inside 400us half-slots stay
        # separate.
        fs = 1_000_000
        pulse_us = 400  # half-slot width; symbol period = 2*400 = 800us
        pulse_narrow_us = 100  # actual pulse width
        half_samples = int(pulse_us * fs / 1_000_000)
        narrow_samples = int(pulse_narrow_us * fs / 1_000_000)
        idle_samples = half_samples - narrow_samples
        bits_ref = [1, 0, 1, 1, 0, 0, 1, 0]
        env_parts = []
        for b in bits_ref:
            if b == 1:
                # Pulse at the start of the symbol slot (first half).
                env_parts.append(np.ones(narrow_samples, dtype=np.float32))
                env_parts.append(np.zeros(idle_samples, dtype=np.float32))
                env_parts.append(np.zeros(half_samples, dtype=np.float32))
            else:
                # Pulse in the second half of the slot.
                env_parts.append(np.zeros(half_samples, dtype=np.float32))
                env_parts.append(np.ones(narrow_samples, dtype=np.float32))
                env_parts.append(np.zeros(idle_samples, dtype=np.float32))
        env = np.concatenate(env_parts)
        iq = env.astype(np.complex64)
        result = decode_ppm(iq, fs, pulse_us=pulse_us)
        assert result["bits"] == bits_ref

    def test_rejects_zero(self) -> None:
        iq = np.ones(1000, dtype=np.complex64)
        with pytest.raises(ValueError, match="must be > 0"):
            decode_ppm(iq, 1_000_000, pulse_us=0)


# ---------------------------------------------------------------------------
# decode_nrz + decode_nrzi
# ---------------------------------------------------------------------------


class TestDecodeNrz:
    def test_recovers_bits(self) -> None:
        bits = [1, 0, 1, 1, 0, 0, 1, 0] * 30
        fs = 1_000_000
        iq = _make_ook(bits, fs=fs, symbol_rate=1000)
        result = decode_nrz(iq, sample_rate_hz=fs, symbol_rate_hz=1000)
        assert result["bits"][: len(bits) - 2] == bits[: len(bits) - 2]

    def test_inverted(self) -> None:
        bits = [1, 0, 1, 0] * 30
        fs = 1_000_000
        iq = _make_ook(bits, fs=fs, symbol_rate=1000)
        result = decode_nrz(
            iq, sample_rate_hz=fs, symbol_rate_hz=1000, inverted=True
        )
        expected = [1 - b for b in bits]
        assert result["bits"][: len(expected) - 2] == expected[: len(expected) - 2]


class TestDecodeNrzi:
    def test_transitions_yield_ones(self) -> None:
        # A stream of alternating levels produces all 1s in NRZI.
        levels = [0, 1] * 30
        fs = 1_000_000
        iq = _make_ook(levels, fs=fs, symbol_rate=1000)
        result = decode_nrzi(iq, sample_rate_hz=fs, symbol_rate_hz=1000)
        # After edge effects, most bits should be 1.
        bits = result["bits"]
        # Allow slight edge losses.
        assert sum(bits) / len(bits) > 0.9

    def test_constant_yields_zeros(self) -> None:
        levels = [1] * 60
        fs = 1_000_000
        iq = _make_ook(levels, fs=fs, symbol_rate=1000)
        result = decode_nrzi(iq, sample_rate_hz=fs, symbol_rate_hz=1000)
        # Constant level → no transitions → all zeros.
        bits = result["bits"]
        assert sum(bits) == 0
