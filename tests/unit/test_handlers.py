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


class TestDispatchTable:
    def test_every_action_has_handler(self) -> None:
        """set(HANDLERS) == set(CommandAction) — every action mapped."""
        assert set(HANDLERS.keys()) == set(CommandAction)
