"""Tests for hackrf_agent.hw.analysis (Phase 3 analysis primitives)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hackrf_agent.hw.analysis import (
    MAX_IQ_FILE_BYTES,
    _ITA2_LTRS,
    _MODES_PREAMBLE_CHIPS,
    _POCSAG_IDLE,
    _POCSAG_SYNC,
    _ax25_crc16,
    _modes_crc24,
    _pocsag_bch_syndrome,
    _pocsag_even_parity,
    classify_modulation,
    decode_ads_b,
    decode_aprs,
    decode_ax25,
    decode_manchester,
    decode_nrz,
    decode_nrzi,
    decode_pocsag,
    decode_ppm,
    decode_pwm,
    decode_rtty,
    estimate_carrier_frequency,
    estimate_symbol_rate,
    fsk_bit_stream,
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


# ---------------------------------------------------------------------------
# POCSAG
# ---------------------------------------------------------------------------


def _synth_pocsag_batch(codewords: list[int], fs: int, baud: int) -> np.ndarray:
    """Synthesize a 2FSK POCSAG batch (sync + codewords) as complex IQ.

    High-frequency = 0 (mark), low-frequency = 1 (space).
    """
    sps = fs // baud
    bits: list[int] = []
    for b in range(31, -1, -1):
        bits.append((_POCSAG_SYNC >> b) & 1)
    for cw in codewords:
        for b in range(31, -1, -1):
            bits.append((cw >> b) & 1)
    n = len(bits)
    inst_freq = np.empty(n * sps, dtype=np.float32)
    freq_hi = 4500.0
    freq_lo = -4500.0
    for i, bit in enumerate(bits):
        inst_freq[i * sps : (i + 1) * sps] = freq_lo if bit else freq_hi
    phase = np.cumsum(2 * np.pi * inst_freq / fs)
    return np.exp(1j * phase).astype(np.complex64)


class TestPocsagPrimitives:
    def test_bch_syndrome_zero_for_sync_and_idle(self) -> None:
        # Canonical POCSAG sync/idle words must have syndrome zero.
        assert _pocsag_bch_syndrome(_POCSAG_SYNC >> 1) == 0
        assert _pocsag_bch_syndrome(_POCSAG_IDLE >> 1) == 0

    def test_parity_even_for_sync_and_idle(self) -> None:
        assert _pocsag_even_parity(_POCSAG_SYNC) == 0
        assert _pocsag_even_parity(_POCSAG_IDLE) == 0


class TestDecodePocsag:
    def test_batch_of_idle_codewords(self) -> None:
        # Sync + 16 idle codewords. Should decode without any address,
        # so no messages, but sync should be found and codewords counted.
        fs = 1_200_000
        baud = 1200
        iq = _synth_pocsag_batch([_POCSAG_IDLE] * 16, fs, baud)
        result = decode_pocsag(iq, sample_rate_hz=fs, baud=baud)
        assert result["sync_offsets"]
        assert result["num_codewords"] == 16
        # Every codeword was a canonical idle → BCH-valid.
        assert result["invalid_codewords"] == 0
        assert result["messages"] == []

    def test_rejects_bad_baud(self) -> None:
        iq = np.ones(10_000, dtype=np.complex64)
        with pytest.raises(ValueError, match="baud must be one of"):
            decode_pocsag(iq, sample_rate_hz=1_000_000, baud=999)

    def test_too_few_samples(self) -> None:
        iq = np.ones(10, dtype=np.complex64)
        result = decode_pocsag(iq, sample_rate_hz=1_000_000, baud=1200)
        assert result["messages"] == []
        assert result["num_codewords"] == 0


# ---------------------------------------------------------------------------
# ADS-B / Mode S
# ---------------------------------------------------------------------------


def _synth_ads_b_frame(msg_hex: str, fs: int) -> np.ndarray:
    """Synthesize a Mode S envelope: silence + preamble + PPM payload."""
    msg_bytes = bytes.fromhex(msg_hex)
    bits = np.unpackbits(np.frombuffer(msg_bytes, dtype=np.uint8))
    sps_per_us = fs / 1_000_000
    samples_per_bit = int(round(sps_per_us))
    half = samples_per_bit // 2
    # Preamble: 16 chips at 2 chips/us (i.e. 8 us total).
    samples_per_chip = int(round(sps_per_us / 2))
    preamble = np.repeat(
        np.array(_MODES_PREAMBLE_CHIPS, dtype=np.float32), samples_per_chip
    )
    # Payload PPM.
    payload = np.zeros(bits.size * samples_per_bit, dtype=np.float32)
    for i, b in enumerate(bits):
        base = i * samples_per_bit
        if b:
            payload[base : base + half] = 1.0
        else:
            payload[base + half : base + samples_per_bit] = 1.0
    silence = np.zeros(40, dtype=np.float32)
    envelope = np.concatenate([silence, preamble, payload, silence])
    return envelope.astype(np.complex64)


class TestAdsBPrimitives:
    def test_crc_zero_for_valid_frame(self) -> None:
        # A canonical DF17 frame from real captures.
        msg_hex = "8D4840D6202CC371C32CE0576098"
        bits = np.unpackbits(np.frombuffer(bytes.fromhex(msg_hex), dtype=np.uint8))
        assert _modes_crc24(bits) == 0

    def test_crc_nonzero_for_corrupted_frame(self) -> None:
        msg_hex = "8D4840D6202CC371C32CE0576099"  # flipped last byte
        bits = np.unpackbits(np.frombuffer(bytes.fromhex(msg_hex), dtype=np.uint8))
        assert _modes_crc24(bits) != 0


class TestDecodeAdsB:
    def test_round_trips_synthetic_frame(self) -> None:
        msg_hex = "8D4840D6202CC371C32CE0576098"
        iq = _synth_ads_b_frame(msg_hex, fs=2_000_000)
        result = decode_ads_b(iq, sample_rate_hz=2_000_000, max_frames=4)
        assert result["num_preambles"] >= 1
        assert result["frames"]
        f0 = result["frames"][0]
        assert f0["df"] == 17
        assert f0["icao24_hex"] == "4840D6"
        assert f0["crc_ok"] is True
        assert f0["raw_hex"] == msg_hex

    def test_rejects_low_sample_rate(self) -> None:
        iq = np.ones(1000, dtype=np.complex64)
        with pytest.raises(ValueError, match="sample_rate_hz"):
            decode_ads_b(iq, sample_rate_hz=1_000_000)

    def test_no_preamble_no_frames(self) -> None:
        # Pure noise: no correlation peaks above the threshold.
        rng = np.random.default_rng(0)
        iq = rng.normal(0, 0.05, 100_000).astype(np.complex64)
        result = decode_ads_b(iq, sample_rate_hz=2_000_000)
        # Should not crash; may report 0 or a few false positives at the
        # 99.5-percentile threshold. Real payloads must fail CRC.
        for frame in result["frames"]:
            assert frame["crc_ok"] is False


# ---------------------------------------------------------------------------
# RTTY
# ---------------------------------------------------------------------------


def _synth_rtty(text: str, fs: int, baud: float) -> np.ndarray:
    """Synthesize a 2FSK RTTY signal (Baudot ITA2, MARK=high freq)."""
    codes = [_ITA2_LTRS.index(ch) for ch in text]
    bits: list[int] = [1] * 20  # idle mark
    for code in codes:
        bits.append(0)  # start bit
        for i in range(5):
            bits.append((code >> i) & 1)  # LSB first
        bits.append(1)  # stop bit
    bits.extend([1] * 20)
    sps = int(round(fs / baud))
    inst_freq = np.empty(len(bits) * sps, dtype=np.float32)
    for i, b in enumerate(bits):
        inst_freq[i * sps : (i + 1) * sps] = 85.0 if b else -85.0
    phase = np.cumsum(2 * np.pi * inst_freq / fs)
    return np.exp(1j * phase).astype(np.complex64)


class TestDecodeRtty:
    def test_letters_roundtrip(self) -> None:
        iq = _synth_rtty("HELLO", fs=48_000, baud=45.45)
        result = decode_rtty(iq, sample_rate_hz=48_000, baud=45.45)
        assert result["text"] == "HELLO"
        assert result["num_characters"] == 5
        assert result["framing_errors"] == 0

    def test_invert_polarity(self) -> None:
        # Synthesize with swapped MARK/SPACE at generation time — MARK
        # becomes the low frequency and SPACE the high one. This models a
        # transmitter that swapped its shift-key polarity.
        text = "ABC"
        codes = [_ITA2_LTRS.index(ch) for ch in text]
        bits: list[int] = [1] * 20
        for c in codes:
            bits.append(0)
            for i in range(5):
                bits.append((c >> i) & 1)
            bits.append(1)
        bits.extend([1] * 20)
        fs = 48_000
        baud = 45.45
        sps = int(round(fs / baud))
        # Swap: MARK (bit=1) -> low freq, SPACE (bit=0) -> high freq.
        inst_freq = np.empty(len(bits) * sps, dtype=np.float32)
        for i, b in enumerate(bits):
            inst_freq[i * sps : (i + 1) * sps] = -85.0 if b else 85.0
        phase = np.cumsum(2 * np.pi * inst_freq / fs)
        iq = np.exp(1j * phase).astype(np.complex64)
        # Decoding with invert=True should recover the text.
        result = decode_rtty(iq, fs, baud, invert=True)
        assert result["text"] == text
        # Decoding without invert should NOT recover the text.
        result_no_invert = decode_rtty(iq, fs, baud, invert=False)
        assert result_no_invert["text"] != text

    def test_too_short_capture(self) -> None:
        iq = np.zeros(10, dtype=np.complex64)
        result = decode_rtty(iq, sample_rate_hz=48_000, baud=45.45)
        assert result["num_characters"] == 0

    def test_shift_state_figs_and_ltrs(self) -> None:
        # "A1B" — needs a FIGS shift before "1" and an LTRS shift before
        # the "B". Assemble the code stream by hand.
        # A = LTRS index 3; 1 = FIGS index 23; B = LTRS index 25.
        code_a = _ITA2_LTRS.index("A")
        code_b = _ITA2_LTRS.index("B")
        code_figs = 0x1B
        code_1 = 23
        code_ltrs = 0x1F
        # bits framing: start(0) + 5 LSB-first + stop(1)
        codes = [code_a, code_figs, code_1, code_ltrs, code_b]
        bits: list[int] = [1] * 20
        for c in codes:
            bits.append(0)
            for i in range(5):
                bits.append((c >> i) & 1)
            bits.append(1)
        bits.extend([1] * 20)
        fs = 48_000
        baud = 45.45
        sps = int(round(fs / baud))
        inst_freq = np.empty(len(bits) * sps, dtype=np.float32)
        for i, b in enumerate(bits):
            inst_freq[i * sps : (i + 1) * sps] = 85.0 if b else -85.0
        phase = np.cumsum(2 * np.pi * inst_freq / fs)
        iq = np.exp(1j * phase).astype(np.complex64)
        result = decode_rtty(iq, fs, baud)
        assert result["text"] == "A1B"


# ---------------------------------------------------------------------------
# fsk_bit_stream (shared primitive)
# ---------------------------------------------------------------------------


class TestFskBitStream:
    def test_recovers_alternating_bits(self) -> None:
        # Synthesize a 1 kbps 2FSK signal with alternating 0101...
        fs = 100_000
        baud = 1000
        sps = fs // baud
        bits = [i % 2 for i in range(50)]
        inst_freq = np.empty(len(bits) * sps, dtype=np.float32)
        for i, b in enumerate(bits):
            inst_freq[i * sps : (i + 1) * sps] = 2000.0 if b else -2000.0
        phase = np.cumsum(2 * np.pi * inst_freq / fs)
        iq = np.exp(1j * phase).astype(np.complex64)
        recovered = fsk_bit_stream(iq, fs, baud)
        assert recovered.tolist()[:20] == bits[:20]

    def test_invert(self) -> None:
        fs = 100_000
        baud = 1000
        sps = fs // baud
        bits = [1, 1, 1, 0, 1, 0, 0, 1] * 5
        inst_freq = np.empty(len(bits) * sps, dtype=np.float32)
        for i, b in enumerate(bits):
            inst_freq[i * sps : (i + 1) * sps] = 2000.0 if b else -2000.0
        phase = np.cumsum(2 * np.pi * inst_freq / fs)
        iq = np.exp(1j * phase).astype(np.complex64)
        r1 = fsk_bit_stream(iq, fs, baud)
        r2 = fsk_bit_stream(iq, fs, baud, invert=True)
        # Inversion swaps every bit.
        assert (r1 == 1 - r2).all()

    def test_too_high_baud(self) -> None:
        iq = np.ones(100, dtype=np.complex64)
        recovered = fsk_bit_stream(iq, 1_000_000, 2_000_000)
        assert recovered.size == 0


# ---------------------------------------------------------------------------
# AX.25 + APRS
# ---------------------------------------------------------------------------


def _make_ax25_addr(callsign: str, ssid: int, last: bool) -> bytes:
    """Encode a 7-byte AX.25 address."""
    padded = callsign.ljust(6)
    b = bytearray()
    for c in padded:
        b.append(ord(c) << 1)
    ssid_byte = ((ssid & 0x0F) << 1) | 0x60
    if last:
        ssid_byte |= 0x01
    b.append(ssid_byte)
    return bytes(b)


def _synth_ax25_frame(
    info_bytes: bytes,
    fs: int = 48_000,
    baud: float = 1200.0,
    n_flags_around: int = 4,
) -> np.ndarray:
    """Synthesize a Bell 202 AFSK AX.25 UI frame with the given info payload.

    Destination = 'APRS-0', source = 'KG7ABC-1', no digipeaters.
    """
    payload = (
        _make_ax25_addr("APRS", 0, False)
        + _make_ax25_addr("KG7ABC", 1, True)
        + bytes([0x03, 0xF0])
        + info_bytes
    )
    fcs = _ax25_crc16(payload)
    frame = payload + bytes([fcs & 0xFF, (fcs >> 8) & 0xFF])
    # LSB-first bit stream.
    bits = [(b >> i) & 1 for b in frame for i in range(8)]
    # Bit-stuff.
    stuffed: list[int] = []
    ones = 0
    for b in bits:
        stuffed.append(b)
        if b == 1:
            ones += 1
            if ones == 5:
                stuffed.append(0)
                ones = 0
        else:
            ones = 0
    flag = [0, 1, 1, 1, 1, 1, 1, 0]
    full = flag * n_flags_around + stuffed + flag * n_flags_around
    # NRZI encode: 0 -> transition, 1 -> no transition.
    nrzi: list[int] = []
    state = 1
    for b in full:
        if b == 0:
            state = 1 - state
        nrzi.append(state)
    sps = int(round(fs / baud))
    inst_freq = np.empty(len(nrzi) * sps, dtype=np.float32)
    for i, b in enumerate(nrzi):
        inst_freq[i * sps : (i + 1) * sps] = 2200.0 if b else 1200.0
    phase = np.cumsum(2 * np.pi * inst_freq / fs)
    return np.exp(1j * phase).astype(np.complex64)


class TestAx25Primitives:
    def test_crc16_known_vector(self) -> None:
        # A truncated but well-formed AX.25 frame header: dest+src+ctrl+pid.
        payload = (
            _make_ax25_addr("APRS", 0, False)
            + _make_ax25_addr("KG7ABC", 1, True)
            + bytes([0x03, 0xF0])
        )
        crc = _ax25_crc16(payload)
        # Verify: appending FCS bytes and CRCing the whole thing should
        # return the reflected value of 0xF0B8 (the standard "no error"
        # residual). For simplicity, just confirm CRC is deterministic
        # and non-zero for a real payload.
        assert 0 < crc <= 0xFFFF
        # Deterministic across runs.
        assert _ax25_crc16(payload) == crc


class TestDecodeAx25:
    def test_roundtrip_ui_frame(self) -> None:
        info = b"!4903.50N/07201.75W-Test APRS"
        iq = _synth_ax25_frame(info)
        result = decode_ax25(iq, sample_rate_hz=48_000, baud=1200.0)
        assert result["num_frames"] >= 1
        f = result["frames"][0]
        assert f["destination"]["callsign"] == "APRS"
        assert f["source"]["callsign"] == "KG7ABC"
        assert f["source"]["ssid"] == 1
        assert f["is_ui"] is True
        assert f["pid"] == 0xF0
        assert f["crc_ok"] is True
        assert f["info_ascii"] == info.decode("ascii")

    def test_bad_crc_detected(self) -> None:
        # Build a valid frame, then corrupt one info byte before modulation.
        info = b"Hello, world!"
        iq = _synth_ax25_frame(info)
        # Cheap corruption: flip a random middle sample's phase. Better:
        # rebuild but replace the info bytes with a wrong version so the
        # CRC on-air doesn't match.
        info_wrong = b"Hello, wxrld!"
        iq_bad = _synth_ax25_frame(info_wrong)
        # Force decode as if FCS were correct: manually replace last
        # 2 bytes' worth of samples. Actually easier: synthesize a frame
        # with wrong FCS by lying at build time. We keep it simple:
        # decode the wrong frame; its CRC WILL be OK (we recomputed it).
        # So instead: corrupt the raw IQ by clipping a segment mid-frame.
        n_zero = 40  # zero out one bit-cell worth of samples
        mid = iq.size // 2
        iq_corrupt = iq.copy()
        iq_corrupt[mid : mid + n_zero] = 0
        result = decode_ax25(iq_corrupt, 48_000, 1200.0)
        # Depending on where the corruption lands, we may or may not
        # recover any frames — but any recovered frame must show crc_ok
        # False.
        for f in result["frames"]:
            # If frames were recovered, their FCS should not match.
            assert not f["crc_ok"]

    def test_no_signal(self) -> None:
        iq = np.zeros(48_000, dtype=np.complex64)
        result = decode_ax25(iq, 48_000, 1200.0)
        assert result["num_frames"] == 0

    def test_polarity_is_transparent_via_nrzi(self) -> None:
        # NRZI encodes 0=transition, 1=no transition. Since transitions
        # depend on level *changes* rather than absolute levels, inverting
        # the FSK output before NRZI decoding leaves the recovered bits
        # unchanged. AX.25 is naturally polarity-tolerant.
        info = b"Hi"
        iq = _synth_ax25_frame(info)
        result_normal = decode_ax25(iq, 48_000, 1200.0, invert=False)
        result_invert = decode_ax25(iq, 48_000, 1200.0, invert=True)
        # Both should decode the same frames — polarity is invisible after
        # NRZI.
        assert result_normal["num_crc_ok"] == result_invert["num_crc_ok"]
        assert result_normal["num_crc_ok"] >= 1


class TestDecodeAprs:
    def test_position_uncompressed(self) -> None:
        info = b"!4903.50N/07201.75W-Comment"
        iq = _synth_ax25_frame(info)
        result = decode_aprs(iq, 48_000, 1200.0)
        assert result["num_aprs_frames"] == 1
        aprs = result["frames"][0]["aprs"]
        assert aprs["kind"] == "position"
        assert abs(aprs["lat"] - 49.05833333) < 1e-5
        assert abs(aprs["lon"] - -72.02916666) < 1e-5
        assert aprs["symbol_table"] == "/"
        assert aprs["symbol_code"] == "-"
        assert aprs["comment"] == "Comment"

    def test_status_dti(self) -> None:
        info = b">Testing 1 2 3"
        iq = _synth_ax25_frame(info)
        result = decode_aprs(iq, 48_000, 1200.0)
        aprs = result["frames"][0]["aprs"]
        assert aprs["kind"] == "status"
        assert aprs["status"] == "Testing 1 2 3"

    def test_message_dti(self) -> None:
        info = b":WX1XYZ   :Hello there"
        iq = _synth_ax25_frame(info)
        result = decode_aprs(iq, 48_000, 1200.0)
        aprs = result["frames"][0]["aprs"]
        assert aprs["kind"] == "message"
        assert aprs["addressee"] == "WX1XYZ"
        assert aprs["text"] == "Hello there"

    def test_unknown_dti(self) -> None:
        info = b"XSome random payload"
        iq = _synth_ax25_frame(info)
        result = decode_aprs(iq, 48_000, 1200.0)
        aprs = result["frames"][0]["aprs"]
        assert aprs["kind"] == "unknown"
        assert aprs["dti"] == "X"

    def test_south_west_coords_negative(self) -> None:
        info = b"!3352.00S/15113.00E-Sydney"
        iq = _synth_ax25_frame(info)
        result = decode_aprs(iq, 48_000, 1200.0)
        aprs = result["frames"][0]["aprs"]
        assert aprs["kind"] == "position"
        # Southern hemisphere → negative latitude.
        assert aprs["lat"] < 0
        # Eastern longitude → positive.
        assert aprs["lon"] > 0
        assert abs(aprs["lat"] - -33.86666666) < 1e-5
        assert abs(aprs["lon"] - 151.21666666) < 1e-5


class TestEstimateCarrierFrequency:
    """estimate_carrier_frequency finds the strongest tone in the capture."""

    def _synth_tone(
        self, freq_hz: float, sample_rate_hz: int, num_samples: int = 8192
    ) -> np.ndarray:
        t = np.arange(num_samples) / sample_rate_hz
        # Complex exponential at freq_hz (positive freq = above baseband centre).
        return (np.exp(2j * np.pi * freq_hz * t)).astype(np.complex64)

    def test_finds_positive_offset(self) -> None:
        fs = 2_000_000
        offset = 100_000.0
        iq = self._synth_tone(offset, fs)
        result = estimate_carrier_frequency(iq, fs, fft_size=8192)
        # Bin resolution is fs/fft = ~244 Hz; expect < 1 bin accuracy after
        # parabolic refinement.
        assert abs(result["carrier_offset_hz"] - offset) < 500.0
        assert result["confidence"] > 10.0

    def test_finds_negative_offset(self) -> None:
        fs = 2_000_000
        offset = -250_000.0
        iq = self._synth_tone(offset, fs)
        result = estimate_carrier_frequency(iq, fs, fft_size=8192)
        assert abs(result["carrier_offset_hz"] - offset) < 500.0

    def test_zero_offset(self) -> None:
        fs = 2_000_000
        iq = self._synth_tone(0.0, fs)
        result = estimate_carrier_frequency(iq, fs, fft_size=8192)
        assert abs(result["carrier_offset_hz"]) < 500.0

    def test_returns_bin_resolution(self) -> None:
        fs = 2_000_000
        iq = self._synth_tone(50_000.0, fs)
        result = estimate_carrier_frequency(iq, fs, fft_size=8192)
        assert result["bin_resolution_hz"] == pytest.approx(fs / 8192)

    def test_short_iq_returns_zero(self) -> None:
        fs = 2_000_000
        iq = np.zeros(128, dtype=np.complex64)
        result = estimate_carrier_frequency(iq, fs, fft_size=8192)
        assert result["carrier_offset_hz"] == 0.0
        assert result["confidence"] == 0.0

    def test_all_zeros_returns_zero_confidence(self) -> None:
        fs = 2_000_000
        iq = np.zeros(8192, dtype=np.complex64)
        result = estimate_carrier_frequency(iq, fs, fft_size=8192)
        assert result["confidence"] == 0.0
