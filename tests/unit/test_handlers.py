"""Tests for handlers.py — one test per handler, using FakeDriver."""

from pathlib import Path

import pytest

from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.handlers import HANDLERS, HandlerContext
from hackrf_agent.domain.models import CommandAction
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.session import new_session
from tests.support.fake_driver import FakeDriver


@pytest.fixture
async def ctx(tmp_path: Path):
    db = tmp_path / "agent.db"
    await ensure_schema(db)
    perms = PermissionService(db)
    driver = FakeDriver()
    async with AuditService(db) as audit:
        yield HandlerContext(
            driver=driver,
            permissions=perms,
            audit=audit,
            session_paths=new_session(tmp_path / "sessions"),
        )


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


class TestGetDeviceInfo:
    async def test_returns_device_info(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.GET_DEVICE_INFO](ctx, {})
        assert result["kind"] == "device_info"
        assert result["info"].serial == "fake-serial"
        assert result["info"].firmware_version == "0.0-fake"


class TestSweepSpectrum:
    async def test_calls_driver_with_mapped_args(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.SWEEP_SPECTRUM](
            ctx,
            {"start_freq_hz": 100_000_000, "end_freq_hz": 200_000_000},
        )
        assert result["kind"] == "sweep"
        assert result["start_hz"] == 100_000_000
        assert result["stop_hz"] == 200_000_000
        assert "magnitude_db" in result
        assert "freqs_hz" in result
        # Driver was called.
        assert len(ctx.driver.calls) >= 1
        assert ctx.driver.calls[0][0] == "sweep_spectrum"


class TestSweepSpectrumBulk:
    async def test_dispatches_all_ranges(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.SWEEP_SPECTRUM_BULK](
            ctx,
            {
                "ranges": [
                    {"start_freq_hz": 315_000_000, "end_freq_hz": 316_000_000},
                    {"start_freq_hz": 433_000_000, "end_freq_hz": 435_000_000},
                    {"start_freq_hz": 902_000_000, "end_freq_hz": 928_000_000},
                ],
            },
        )
        assert result["kind"] == "sweep_bulk"
        assert len(result["sweeps"]) == 3
        # Driver called once per range.
        assert len([c for c in ctx.driver.calls if c[0] == "sweep_spectrum"]) == 3

    async def test_shares_settings_across_ranges(
        self, ctx: HandlerContext
    ) -> None:
        await HANDLERS[CommandAction.SWEEP_SPECTRUM_BULK](
            ctx,
            {
                "ranges": [
                    {"start_freq_hz": 315_000_000, "end_freq_hz": 316_000_000},
                    {"start_freq_hz": 433_000_000, "end_freq_hz": 435_000_000},
                ],
                "sample_rate_hz": 4_000_000,
                "dwell_s": 0.5,
                "fft_size": 2048,
            },
        )
        for name, kwargs in ctx.driver.calls:
            if name == "sweep_spectrum":
                assert kwargs["sample_rate_hz"] == 4_000_000
                assert kwargs["dwell_s"] == 0.5
                assert kwargs["fft_size"] == 2048

    async def test_rejects_single_range(self, ctx: HandlerContext) -> None:
        with pytest.raises(Exception):
            await HANDLERS[CommandAction.SWEEP_SPECTRUM_BULK](
                ctx,
                {"ranges": [
                    {"start_freq_hz": 433_000_000, "end_freq_hz": 434_000_000}
                ]},
            )

    async def test_rejects_reversed_range(self, ctx: HandlerContext) -> None:
        with pytest.raises(Exception):
            await HANDLERS[CommandAction.SWEEP_SPECTRUM_BULK](
                ctx,
                {"ranges": [
                    {"start_freq_hz": 434_000_000, "end_freq_hz": 433_000_000},
                    {"start_freq_hz": 315_000_000, "end_freq_hz": 316_000_000},
                ]},
            )


class TestCaptureIq:
    async def test_writes_to_session_iq_dir(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.CAPTURE_IQ](
            ctx,
            {"center_freq_hz": 433_000_000, "duration_s": 0.1},
        )
        assert result["kind"] == "capture"
        # Driver was called with an out_path under iq_dir.
        assert len(ctx.driver.calls) >= 1
        call_name, call_kwargs = ctx.driver.calls[0]
        assert call_name == "capture_iq"
        out_path = call_kwargs["out_path"]
        assert ctx.session_paths.is_within(out_path)

    async def test_out_path_exists_after_call(self, ctx: HandlerContext) -> None:
        await HANDLERS[CommandAction.CAPTURE_IQ](
            ctx,
            {"center_freq_hz": 433_000_000, "duration_s": 0.1},
        )
        call_kwargs = ctx.driver.calls[0][1]
        assert call_kwargs["out_path"].is_file()


class TestTransmitIq:
    async def test_path_outside_root_raises(self, ctx: HandlerContext) -> None:
        with pytest.raises(ValueError, match="escapes session root"):
            await HANDLERS[CommandAction.TRANSMIT_IQ](
                ctx,
                {
                    "center_freq_hz": 433_000_000,
                    "tx_vga_gain_db": 20,
                    "iq_path": "/tmp/outside.iq",
                },
            )

    async def test_nonexistent_path_raises(self, ctx: HandlerContext) -> None:
        iq_path = ctx.session_paths.new_iq_path("test")
        # Don't create the file.
        with pytest.raises(ValueError, match="does not exist"):
            await HANDLERS[CommandAction.TRANSMIT_IQ](
                ctx,
                {
                    "center_freq_hz": 433_000_000,
                    "tx_vga_gain_db": 20,
                    "iq_path": str(iq_path),
                },
            )

    async def test_happy_path(self, ctx: HandlerContext) -> None:
        # Create a minimal IQ file inside session root.
        iq_path = ctx.session_paths.new_iq_path("tx-test")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(b"\x00\x01" * 100)

        result = await HANDLERS[CommandAction.TRANSMIT_IQ](
            ctx,
            {
                "center_freq_hz": 433_000_000,
                "tx_vga_gain_db": 20,
                "iq_path": str(iq_path),
            },
        )
        assert result["kind"] == "transmit"
        assert "duration_s" in result
        assert result["duration_s"] >= 0
        assert len(ctx.driver.calls) >= 1
        assert ctx.driver.calls[0][0] == "transmit_iq"


class TestReadIqSummary:
    async def test_path_outside_root_raises(self, ctx: HandlerContext) -> None:
        with pytest.raises(ValueError, match="escapes session root"):
            await HANDLERS[CommandAction.READ_IQ_SUMMARY](
                ctx,
                {
                    "center_freq_hz": 433_000_000,
                    "iq_path": "/tmp/outside.iq",
                },
            )


class TestGrantList:
    async def test_empty_grants(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.GRANT_LIST](ctx, {})
        assert result["kind"] == "grant_list"
        assert result["grants"] == []

    async def test_one_grant(self, ctx: HandlerContext) -> None:
        await ctx.permissions.grant(
            kind="tx",
            band_start_hz=433_000_000,
            band_stop_hz=434_000_000,
            max_gain_db=30,
            ttl_seconds=3600,
        )
        result = await HANDLERS[CommandAction.GRANT_LIST](ctx, {})
        assert len(result["grants"]) == 1


class TestAuditQuery:
    async def test_empty_audit(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.AUDIT_QUERY](ctx, {})
        assert result["kind"] == "audit_query"
        assert result["rows"] == []


class TestDecodeOok:
    async def test_placeholder(self, ctx: HandlerContext) -> None:
        iq_path = ctx.session_paths.new_iq_path("ook")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(b"\x00\x01" * 50)

        result = await HANDLERS[CommandAction.DECODE_OOK](ctx, {"iq_path": str(iq_path)})
        assert result["kind"] == "decode_ook"
        # No driver calls.
        assert len(ctx.driver.calls) == 0


class TestAnalysisHandlers:
    """Analysis handlers read an .iq file from the session dir and produce
    JSON-primitive summaries. None invokes the driver."""

    async def _write_ook_iq(
        self, ctx: HandlerContext, bits: list[int], symbol_rate: int, fs: int
    ) -> str:
        """Author an int8-interleaved OOK IQ file under session root."""
        import numpy as np

        sps = fs // symbol_rate
        env = np.repeat(np.array(bits, dtype=np.float32), sps) * 0.9 + 0.05
        # HackRF native format: int8 interleaved I/Q.
        i_samples = (env * 127).astype(np.int8)
        q_samples = np.zeros_like(i_samples)
        interleaved = np.empty(2 * i_samples.size, dtype=np.int8)
        interleaved[0::2] = i_samples
        interleaved[1::2] = q_samples
        iq_path = ctx.session_paths.new_iq_path("ook-test")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(interleaved.tobytes())
        return str(iq_path)

    async def test_analyze_iq_modulation(self, ctx: HandlerContext) -> None:
        path = await self._write_ook_iq(
            ctx, bits=[1, 0, 1, 1, 0, 0, 1, 0] * 30, symbol_rate=1000, fs=1_000_000
        )
        result = await HANDLERS[CommandAction.ANALYZE_IQ_MODULATION](
            ctx, {"iq_path": path, "sample_rate_hz": 1_000_000}
        )
        assert result["candidates"]
        assert result["candidates"][0]["family"] == "OOK"
        assert len(ctx.driver.calls) == 0

    async def test_analyze_iq_modulation_rejects_outside_root(
        self, ctx: HandlerContext
    ) -> None:
        with pytest.raises(ValueError, match="escapes session root"):
            await HANDLERS[CommandAction.ANALYZE_IQ_MODULATION](
                ctx, {"iq_path": "/tmp/outside.iq", "sample_rate_hz": 1_000_000}
            )

    async def test_analyze_iq_symbols(self, ctx: HandlerContext) -> None:
        import numpy as np
        rng = np.random.default_rng(1)
        bits = rng.integers(0, 2, 400).tolist()
        path = await self._write_ook_iq(
            ctx, bits=bits, symbol_rate=1000, fs=1_000_000
        )
        result = await HANDLERS[CommandAction.ANALYZE_IQ_SYMBOLS](
            ctx, {"iq_path": path, "sample_rate_hz": 1_000_000}
        )
        assert abs(result["symbol_rate_hz"] - 1000) < 50
        assert result["confidence"] > 0.5
        assert len(ctx.driver.calls) == 0

    async def test_analyze_iq_spectrogram(self, ctx: HandlerContext) -> None:
        # Need enough samples for a 1024-point FFT. 8 kbps at 1 MSps for
        # 200 bits = 200 * 125 = 25000 samples — plenty.
        path = await self._write_ook_iq(
            ctx, bits=[1, 0] * 100, symbol_rate=8000, fs=1_000_000
        )
        result = await HANDLERS[CommandAction.ANALYZE_IQ_SPECTROGRAM](
            ctx,
            {
                "iq_path": path,
                "sample_rate_hz": 1_000_000,
                "fft_size": 1024,
                "overlap": 0.5,
                "max_slices": 32,
            },
        )
        assert result["num_slices"] > 0
        assert len(result["peak_freqs_hz"]) == result["num_slices"]

    async def test_decode_manchester(self, ctx: HandlerContext) -> None:
        # Manchester at 1 kbps means half-symbols at 2 kHz.
        bits = [1, 0, 1, 1, 0, 0, 1, 0] * 10
        pairs: list[int] = []
        for b in bits:
            pairs.extend([0, 1] if b == 1 else [1, 0])
        path = await self._write_ook_iq(
            ctx, bits=pairs, symbol_rate=2000, fs=1_000_000
        )
        result = await HANDLERS[CommandAction.DECODE_MANCHESTER](
            ctx,
            {
                "iq_path": path,
                "sample_rate_hz": 1_000_000,
                "symbol_rate_hz": 1000.0,
                "polarity": "ieee",
            },
        )
        recovered = result["bits"][: len(bits) - 1]
        assert recovered == bits[: len(bits) - 1]

    async def test_decode_pwm(self, ctx: HandlerContext) -> None:
        import numpy as np
        fs = 1_000_000
        short_samples = 400  # 400 us at 1 MSps
        long_samples = 800
        gap_samples = 400
        bits_ref = [0, 1, 0, 1, 1, 0, 1, 0]
        env_parts = []
        for b in bits_ref:
            width = long_samples if b == 1 else short_samples
            env_parts.append(np.ones(width, dtype=np.float32))
            env_parts.append(np.zeros(gap_samples, dtype=np.float32))
        env = np.concatenate(env_parts)
        i8 = (env * 0.9 * 127).astype(np.int8)
        q8 = np.zeros_like(i8)
        interleaved = np.empty(2 * i8.size, dtype=np.int8)
        interleaved[0::2] = i8
        interleaved[1::2] = q8
        iq_path = ctx.session_paths.new_iq_path("pwm-test")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(interleaved.tobytes())
        result = await HANDLERS[CommandAction.DECODE_PWM](
            ctx,
            {
                "iq_path": str(iq_path),
                "sample_rate_hz": fs,
                "short_us": 400,
                "long_us": 800,
            },
        )
        assert result["bits"] == bits_ref

    async def test_decode_nrz(self, ctx: HandlerContext) -> None:
        bits = [1, 0, 1, 1, 0, 0, 1, 0] * 30
        path = await self._write_ook_iq(
            ctx, bits=bits, symbol_rate=1000, fs=1_000_000
        )
        result = await HANDLERS[CommandAction.DECODE_NRZ](
            ctx,
            {
                "iq_path": path,
                "sample_rate_hz": 1_000_000,
                "symbol_rate_hz": 1000.0,
                "variant": "nrz",
            },
        )
        assert result["bits"][: len(bits) - 2] == bits[: len(bits) - 2]

    async def test_decode_nrz_variant_nrzi(self, ctx: HandlerContext) -> None:
        # Constant HIGH → NRZI produces zeros.
        levels = [1] * 100
        path = await self._write_ook_iq(
            ctx, bits=levels, symbol_rate=1000, fs=1_000_000
        )
        result = await HANDLERS[CommandAction.DECODE_NRZ](
            ctx,
            {
                "iq_path": path,
                "sample_rate_hz": 1_000_000,
                "symbol_rate_hz": 1000.0,
                "variant": "nrzi",
            },
        )
        assert sum(result["bits"]) == 0

    async def test_decode_ax25_and_aprs(self, ctx: HandlerContext) -> None:
        import numpy as np
        # Build an AX.25 UI frame with an APRS position payload.
        def make_addr(cs, ssid, last):
            padded = cs.ljust(6)
            b = bytearray()
            for c in padded:
                b.append(ord(c) << 1)
            b.append(((ssid & 0x0F) << 1) | 0x60 | (0x01 if last else 0))
            return bytes(b)
        from hackrf_agent.hw.analysis import _ax25_crc16
        payload = (
            make_addr("APRS", 0, False)
            + make_addr("KG7ABC", 1, True)
            + bytes([0x03, 0xF0])
            + b"!4903.50N/07201.75W-CTF"
        )
        fcs = _ax25_crc16(payload)
        frame = payload + bytes([fcs & 0xFF, (fcs >> 8) & 0xFF])
        bits = [(b >> i) & 1 for b in frame for i in range(8)]
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
        full = flag * 4 + stuffed + flag * 4
        nrzi: list[int] = []
        state = 1
        for b in full:
            if b == 0:
                state = 1 - state
            nrzi.append(state)
        fs = 48_000
        baud = 1200
        sps = fs // baud
        inst_freq = np.empty(len(nrzi) * sps, dtype=np.float32)
        for i, b in enumerate(nrzi):
            inst_freq[i * sps : (i + 1) * sps] = 2200.0 if b else 1200.0
        phase = np.cumsum(2 * np.pi * inst_freq / fs)
        iq = np.exp(1j * phase).astype(np.complex64)
        i8 = (iq.real * 127).astype(np.int8)
        q8 = (iq.imag * 127).astype(np.int8)
        interleaved = np.empty(2 * i8.size, dtype=np.int8)
        interleaved[0::2] = i8
        interleaved[1::2] = q8
        iq_path = ctx.session_paths.new_iq_path("aprs-test")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(interleaved.tobytes())

        ax25_result = await HANDLERS[CommandAction.DECODE_AX25](
            ctx, {"iq_path": str(iq_path), "sample_rate_hz": fs, "baud": baud}
        )
        assert ax25_result["num_crc_ok"] >= 1
        assert ax25_result["frames"][0]["destination"]["callsign"] == "APRS"

        aprs_result = await HANDLERS[CommandAction.DECODE_APRS](
            ctx, {"iq_path": str(iq_path), "sample_rate_hz": fs, "baud": baud}
        )
        assert aprs_result["num_aprs_frames"] >= 1
        aprs = aprs_result["frames"][0]["aprs"]
        assert aprs["kind"] == "position"
        assert abs(aprs["lat"] - 49.058333) < 1e-4

    async def test_decode_rtty(self, ctx: HandlerContext) -> None:
        import numpy as np
        from hackrf_agent.hw.analysis import _ITA2_LTRS
        fs = 48_000
        baud = 45.45
        text = "HI"
        codes = [_ITA2_LTRS.index(ch) for ch in text]
        bits: list[int] = [1] * 20
        for c in codes:
            bits.append(0)
            for i in range(5):
                bits.append((c >> i) & 1)
            bits.append(1)
        bits.extend([1] * 20)
        sps = int(round(fs / baud))
        inst_freq = np.empty(len(bits) * sps, dtype=np.float32)
        for i, b in enumerate(bits):
            inst_freq[i * sps : (i + 1) * sps] = 85.0 if b else -85.0
        phase = np.cumsum(2 * np.pi * inst_freq / fs)
        iq = np.exp(1j * phase).astype(np.complex64)
        i8 = (iq.real * 127).astype(np.int8)
        q8 = (iq.imag * 127).astype(np.int8)
        interleaved = np.empty(2 * i8.size, dtype=np.int8)
        interleaved[0::2] = i8
        interleaved[1::2] = q8
        iq_path = ctx.session_paths.new_iq_path("rtty-test")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(interleaved.tobytes())
        result = await HANDLERS[CommandAction.DECODE_RTTY](
            ctx,
            {"iq_path": str(iq_path), "sample_rate_hz": fs, "baud": baud},
        )
        assert result["text"] == text
        assert result["framing_errors"] == 0

    async def test_decode_pocsag(self, ctx: HandlerContext) -> None:
        import numpy as np
        from hackrf_agent.hw.analysis import _POCSAG_IDLE, _POCSAG_SYNC
        fs = 1_200_000
        baud = 1200
        sps = fs // baud
        # Sync + 16 idle codewords.
        bits: list[int] = []
        for b in range(31, -1, -1):
            bits.append((_POCSAG_SYNC >> b) & 1)
        for _ in range(16):
            for b in range(31, -1, -1):
                bits.append((_POCSAG_IDLE >> b) & 1)
        inst_freq = np.empty(len(bits) * sps, dtype=np.float32)
        for i, bit in enumerate(bits):
            inst_freq[i * sps : (i + 1) * sps] = -4500.0 if bit else 4500.0
        phase = np.cumsum(2 * np.pi * inst_freq / fs)
        iq = np.exp(1j * phase).astype(np.complex64)
        # HackRF native format: int8 interleaved I/Q.
        i8 = (iq.real * 127).astype(np.int8)
        q8 = (iq.imag * 127).astype(np.int8)
        interleaved = np.empty(2 * i8.size, dtype=np.int8)
        interleaved[0::2] = i8
        interleaved[1::2] = q8
        iq_path = ctx.session_paths.new_iq_path("pocsag-test")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(interleaved.tobytes())
        result = await HANDLERS[CommandAction.DECODE_POCSAG](
            ctx,
            {
                "iq_path": str(iq_path),
                "sample_rate_hz": fs,
                "baud": baud,
            },
        )
        assert result["sync_offsets"]
        assert result["num_codewords"] == 16
        assert result["invalid_codewords"] == 0

    async def test_decode_ads_b(self, ctx: HandlerContext) -> None:
        import numpy as np
        from hackrf_agent.hw.analysis import _MODES_PREAMBLE_CHIPS
        fs = 2_000_000
        msg_hex = "8D4840D6202CC371C32CE0576098"
        msg_bytes = bytes.fromhex(msg_hex)
        bits = np.unpackbits(np.frombuffer(msg_bytes, dtype=np.uint8))
        sps_per_us = fs / 1_000_000
        samples_per_bit = int(round(sps_per_us))
        half = samples_per_bit // 2
        samples_per_chip = int(round(sps_per_us / 2))
        preamble = np.repeat(
            np.array(_MODES_PREAMBLE_CHIPS, dtype=np.float32),
            samples_per_chip,
        )
        payload = np.zeros(bits.size * samples_per_bit, dtype=np.float32)
        for i, b in enumerate(bits):
            base = i * samples_per_bit
            if b:
                payload[base : base + half] = 1.0
            else:
                payload[base + half : base + samples_per_bit] = 1.0
        silence = np.zeros(40, dtype=np.float32)
        envelope = np.concatenate([silence, preamble, payload, silence])
        iq = envelope.astype(np.complex64)
        i8 = (iq.real * 127).astype(np.int8)
        q8 = np.zeros_like(i8)
        interleaved = np.empty(2 * i8.size, dtype=np.int8)
        interleaved[0::2] = i8
        interleaved[1::2] = q8
        iq_path = ctx.session_paths.new_iq_path("adsb-test")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(interleaved.tobytes())
        result = await HANDLERS[CommandAction.DECODE_ADS_B](
            ctx,
            {"iq_path": str(iq_path), "sample_rate_hz": fs},
        )
        assert result["frames"]
        f0 = result["frames"][0]
        assert f0["df"] == 17
        assert f0["icao24_hex"] == "4840D6"
        assert f0["crc_ok"] is True

    async def test_decode_ppm(self, ctx: HandlerContext) -> None:
        import numpy as np
        fs = 1_000_000
        pulse_us = 400
        narrow_us = 100
        half = int(pulse_us * fs / 1_000_000)
        narrow = int(narrow_us * fs / 1_000_000)
        idle = half - narrow
        bits_ref = [1, 0, 1, 1, 0, 0, 1, 0]
        env_parts = []
        for b in bits_ref:
            if b == 1:
                env_parts.append(np.ones(narrow, dtype=np.float32))
                env_parts.append(np.zeros(idle, dtype=np.float32))
                env_parts.append(np.zeros(half, dtype=np.float32))
            else:
                env_parts.append(np.zeros(half, dtype=np.float32))
                env_parts.append(np.ones(narrow, dtype=np.float32))
                env_parts.append(np.zeros(idle, dtype=np.float32))
        env = np.concatenate(env_parts)
        i8 = (env * 0.9 * 127).astype(np.int8)
        q8 = np.zeros_like(i8)
        interleaved = np.empty(2 * i8.size, dtype=np.int8)
        interleaved[0::2] = i8
        interleaved[1::2] = q8
        iq_path = ctx.session_paths.new_iq_path("ppm-test")
        iq_path.parent.mkdir(parents=True, exist_ok=True)
        iq_path.write_bytes(interleaved.tobytes())
        result = await HANDLERS[CommandAction.DECODE_PPM](
            ctx,
            {
                "iq_path": str(iq_path),
                "sample_rate_hz": fs,
                "pulse_us": pulse_us,
            },
        )
        assert result["bits"] == bits_ref


class TestKnowledgeHandlers:
    """Every knowledge handler is read-only and never invokes the driver."""

    async def test_list_topics(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_LIST_TOPICS](ctx, {})
        assert "topics" in result
        assert isinstance(result["topics"], list)
        assert len(ctx.driver.calls) == 0

    async def test_read(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_READ](
            ctx, {"topic": "dsp", "name": "reference.md"}
        )
        assert result["kind"] == "knowledge_read"
        assert result["topic"] == "dsp"
        assert "content" in result
        assert len(ctx.driver.calls) == 0

    async def test_search(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_SEARCH](
            ctx, {"query": "Nyquist", "max_results": 5}
        )
        assert "hits" in result
        assert isinstance(result["hits"], list)
        assert len(ctx.driver.calls) == 0

    async def test_lookup_band_matches_iq_433(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_LOOKUP_BAND](
            ctx, {"freq_hz": 433_920_000}
        )
        ids = [r["id"] for r in result["matches"]]
        assert "band-ism-433" in ids
        assert len(ctx.driver.calls) == 0

    async def test_lookup_band_flags_blocked_at_1090(
        self, ctx: HandlerContext
    ) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_LOOKUP_BAND](
            ctx, {"freq_hz": 1_090_000_000}
        )
        assert result["matches"]
        assert any(r.get("blocked_tx") for r in result["matches"])

    async def test_lookup_modulation(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_LOOKUP_MODULATION](
            ctx, {"name": "GFSK"}
        )
        assert result["record"] is not None
        assert result["record"]["id"] == "modulation-gfsk"
        assert len(ctx.driver.calls) == 0

    async def test_lookup_modulation_miss_returns_none(
        self, ctx: HandlerContext
    ) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_LOOKUP_MODULATION](
            ctx, {"name": "not-a-real-mod"}
        )
        assert result["record"] is None

    async def test_verify_claim_false_on_ads_b_tx(
        self, ctx: HandlerContext
    ) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_VERIFY_CLAIM](
            ctx, {"text": "the hackrf can tx on ADS-B"}
        )
        assert result["verdict"] == "false"
        assert len(ctx.driver.calls) == 0

    async def test_verify_claim_unverified(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_VERIFY_CLAIM](
            ctx, {"text": "yesterday was Tuesday"}
        )
        assert result["verdict"] == "unverified"


class TestExtendedKnowledgeHandlers:
    """Handlers for the seven additional Phase 3 knowledge verbs."""

    async def test_lookup_protocol_pocsag(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_LOOKUP_PROTOCOL](
            ctx, {"name": "POCSAG"}
        )
        assert result["kind"] == "knowledge_lookup_protocol"
        assert result["record"] is not None
        assert "pocsag" in result["record"]["id"]
        assert len(ctx.driver.calls) == 0

    async def test_lookup_protocol_miss(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_LOOKUP_PROTOCOL](
            ctx, {"name": "not-a-real-protocol"}
        )
        assert result["record"] is None

    async def test_lookup_decoder_manchester(
        self, ctx: HandlerContext
    ) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_LOOKUP_DECODER](
            ctx, {"name": "Manchester"}
        )
        assert result["kind"] == "knowledge_lookup_decoder"
        assert result["record"] is not None
        assert "manchester" in result["record"]["id"]

    async def test_lookup_keyfob_by_vendor(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_LOOKUP_KEYFOB](
            ctx, {"vendor": "Chamberlain"}
        )
        assert result["kind"] == "knowledge_lookup_keyfob"
        assert isinstance(result["matches"], list)
        # Real corpus has Chamberlain records.
        assert result["matches"]

    async def test_lookup_keyfob_requires_a_hint(
        self, ctx: HandlerContext
    ) -> None:
        with pytest.raises(Exception):
            await HANDLERS[CommandAction.KNOWLEDGE_LOOKUP_KEYFOB](ctx, {})

    async def test_bibliography_by_id(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_BIBLIOGRAPHY](
            ctx, {"cite_id": "fcc-part-15"}
        )
        assert result["kind"] == "knowledge_bibliography"
        assert len(result["records"]) == 1
        assert result["records"][0]["id"] == "fcc-part-15"

    async def test_bibliography_full_list(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_BIBLIOGRAPHY](ctx, {})
        assert len(result["records"]) >= 2

    async def test_random_deterministic(self, ctx: HandlerContext) -> None:
        a = await HANDLERS[CommandAction.KNOWLEDGE_RANDOM](ctx, {"seed": 7})
        b = await HANDLERS[CommandAction.KNOWLEDGE_RANDOM](ctx, {"seed": 7})
        assert a["topic"] == b["topic"]
        assert a["name"] == b["name"]

    async def test_explain_signal_by_freq(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_EXPLAIN_SIGNAL](
            ctx, {"freq_hz": 433_920_000, "modulation_guess": "OOK"}
        )
        assert result["kind"] == "knowledge_explain_signal"
        assert isinstance(result["candidates"], list)
        assert result["candidates"]

    async def test_explain_signal_requires_a_hint(
        self, ctx: HandlerContext
    ) -> None:
        with pytest.raises(Exception):
            await HANDLERS[CommandAction.KNOWLEDGE_EXPLAIN_SIGNAL](ctx, {})

    async def test_cross_reference_pocsag(self, ctx: HandlerContext) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_CROSS_REFERENCE](
            ctx, {"record_id": "protocol-pocsag-1200"}
        )
        assert result["kind"] == "knowledge_cross_reference"
        assert result["record"] is not None
        # POCSAG record cross-references its 512/2400 siblings and 2FSK
        # modulation record — at least one should resolve.
        assert result["related"], "expected at least one resolved see_also"

    async def test_cross_reference_unknown_record(
        self, ctx: HandlerContext
    ) -> None:
        result = await HANDLERS[CommandAction.KNOWLEDGE_CROSS_REFERENCE](
            ctx, {"record_id": "no-such-record-id"}
        )
        assert result["record"] is None
        assert result["related"] == []


class TestDispatchTable:
    def test_every_action_has_handler(self) -> None:
        """set(HANDLERS) == set(CommandAction) — every action mapped."""
        assert set(HANDLERS.keys()) == set(CommandAction)
