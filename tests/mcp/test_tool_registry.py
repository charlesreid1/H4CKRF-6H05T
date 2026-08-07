"""Unit tests for tool_registry — tool schemas + dispatch."""

from __future__ import annotations

import pytest
from mcp.types import CallToolRequestParams, Tool

from hackrf_agent.domain.models import CommandAction, ExecuteCommand
from hackrf_agent.mcp.tool_registry import (
    ALL_TOOLS,
    build_tool,
    dispatch,
    list_tools,
)


class TestBuildTool:
    """Each CommandAction maps to a valid MCP Tool."""

    def test_every_action_has_a_tool(self) -> None:
        for action in CommandAction:
            assert action.value in ALL_TOOLS, f"Missing tool for {action.value}"

    def test_tool_name_prefixed_with_hackrf(self) -> None:
        for tool in ALL_TOOLS.values():
            assert tool.name.startswith("hackrf_"), f"Bad name: {tool.name}"

    def test_tool_has_input_schema(self) -> None:
        for tool in ALL_TOOLS.values():
            schema = tool.input_schema
            assert isinstance(schema, dict)
            assert schema.get("type") == "object"

    def test_every_tool_requires_justification_and_expected_effect(self) -> None:
        for tool in ALL_TOOLS.values():
            required: list[str] = tool.input_schema.get("required", [])
            assert "justification" in required, f"{tool.name} missing justification"
            assert "expected_effect" in required, f"{tool.name} missing expected_effect"

    def test_sweep_spectrum_has_start_freq_hz(self) -> None:
        tool = ALL_TOOLS["sweep_spectrum"]
        props = tool.input_schema.get("properties", {})
        assert "start_freq_hz" in props
        assert props["start_freq_hz"]["type"] == "integer"

    def test_capture_iq_requires_duration_s(self) -> None:
        tool = ALL_TOOLS["capture_iq"]
        required: list[str] = tool.input_schema.get("required", [])
        assert "duration_s" in required

    def test_transmit_iq_requires_tx_vga_gain_db(self) -> None:
        tool = ALL_TOOLS["transmit_iq"]
        required: list[str] = tool.input_schema.get("required", [])
        assert "tx_vga_gain_db" in required

    def test_get_device_info_no_action_args(self) -> None:
        tool = ALL_TOOLS["get_device_info"]
        required: list[str] = tool.input_schema.get("required", [])
        # Only justification and expected_effect.
        assert set(required) == {"justification", "expected_effect"}

    def test_list_tools_returns_all(self) -> None:
        tools = list_tools()
        assert len(tools) == len(CommandAction)


class TestDispatch:
    """Building ExecuteCommand objects from tool name + arguments dict."""

    def test_sweep_spectrum_dispatch(self) -> None:
        cmd = dispatch(
            "hackrf_sweep_spectrum",
            {
                "start_freq_hz": 433_000_000,
                "end_freq_hz": 434_000_000,
                "justification": "Check ISM band",
                "expected_effect": "See activity peaks",
            },
        )
        assert cmd.action == CommandAction.SWEEP_SPECTRUM
        assert cmd.args["start_freq_hz"] == 433_000_000
        assert cmd.args["end_freq_hz"] == 434_000_000
        assert cmd.args["dwell_s"] == 1.0  # default
        assert cmd.justification == "Check ISM band"

    def test_sweep_spectrum_applies_defaults(self) -> None:
        cmd = dispatch(
            "hackrf_sweep_spectrum",
            {
                "start_freq_hz": 100_000_000,
                "end_freq_hz": 200_000_000,
                "justification": "test",
                "expected_effect": "test",
            },
        )
        assert cmd.args["sample_rate_hz"] == 2_000_000
        assert cmd.args["lna_gain_db"] == 16
        assert cmd.args["vga_gain_db"] == 20

    def test_sweep_spectrum_missing_required_raises(self) -> None:
        with pytest.raises(Exception):
            dispatch(
                "hackrf_sweep_spectrum",
                {
                    "justification": "missing start_freq_hz",
                    "expected_effect": "should fail",
                },
            )

    def test_get_device_info_dispatch(self) -> None:
        cmd = dispatch(
            "hackrf_get_device_info",
            {
                "justification": "Identify radio",
                "expected_effect": "Return serial/firmware",
            },
        )
        assert cmd.action == CommandAction.GET_DEVICE_INFO
        assert cmd.args == {}

    def test_capture_iq_dispatch(self) -> None:
        cmd = dispatch(
            "hackrf_capture_iq",
            {
                "center_freq_hz": 433_000_000,
                "duration_s": 2.0,
                "justification": "Short capture",
                "expected_effect": "IQ file written",
            },
        )
        assert cmd.action == CommandAction.CAPTURE_IQ
        assert cmd.args["center_freq_hz"] == 433_000_000
        assert cmd.args["duration_s"] == 2.0

    def test_transmit_iq_dispatch(self) -> None:
        cmd = dispatch(
            "hackrf_transmit_iq",
            {
                "center_freq_hz": 433_000_000,
                "iq_path": "/tmp/test.iq",
                "tx_vga_gain_db": 10,
                "justification": "Test TX",
                "expected_effect": "Signal transmitted",
            },
        )
        assert cmd.action == CommandAction.TRANSMIT_IQ
        assert cmd.args["tx_vga_gain_db"] == 10

    def test_unknown_tool_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown action"):
            dispatch(
                "hackrf_nonexistent",
                {"justification": "x", "expected_effect": "y"},
            )

    def test_tool_name_without_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown tool"):
            dispatch(
                "sweep_spectrum",
                {"justification": "x", "expected_effect": "y"},
            )

    def test_audit_query_dispatch(self) -> None:
        cmd = dispatch(
            "hackrf_audit_query",
            {
                "limit": 25,
                "justification": "Review recent activity",
                "expected_effect": "List of recent audit events",
            },
        )
        assert cmd.action == CommandAction.AUDIT_QUERY
        assert cmd.args["limit"] == 25

    def test_grant_list_dispatch(self) -> None:
        cmd = dispatch(
            "hackrf_grant_list",
            {
                "justification": "Check active grants",
                "expected_effect": "List of active TX grants",
            },
        )
        assert cmd.action == CommandAction.GRANT_LIST
        assert cmd.args == {}


class TestAnalysisDispatch:
    """Dispatch surface for the analysis tier — args round-trip."""

    def test_analyze_iq_modulation(self) -> None:
        cmd = dispatch(
            "hackrf_analyze_iq_modulation",
            {
                "iq_path": "/tmp/x.iq",
                "sample_rate_hz": 4_000_000,
                "justification": "Identify the modulation",
                "expected_effect": "Ranked candidates",
            },
        )
        assert cmd.action == CommandAction.ANALYZE_IQ_MODULATION
        assert cmd.args["iq_path"] == "/tmp/x.iq"
        assert cmd.args["sample_rate_hz"] == 4_000_000

    def test_analyze_iq_symbols_defaults(self) -> None:
        cmd = dispatch(
            "hackrf_analyze_iq_symbols",
            {
                "iq_path": "/tmp/x.iq",
                "justification": "Find symbol rate",
                "expected_effect": "Rate + confidence",
            },
        )
        assert cmd.action == CommandAction.ANALYZE_IQ_SYMBOLS
        assert cmd.args["sample_rate_hz"] == 2_000_000
        assert cmd.args["min_rate_hz"] == 100.0

    def test_analyze_iq_spectrogram(self) -> None:
        cmd = dispatch(
            "hackrf_analyze_iq_spectrogram",
            {
                "iq_path": "/tmp/x.iq",
                "fft_size": 2048,
                "justification": "Draw spectrogram",
                "expected_effect": "Peak-per-slice array",
            },
        )
        assert cmd.action == CommandAction.ANALYZE_IQ_SPECTROGRAM
        assert cmd.args["fft_size"] == 2048

    def test_decode_manchester(self) -> None:
        cmd = dispatch(
            "hackrf_decode_manchester",
            {
                "iq_path": "/tmp/x.iq",
                "symbol_rate_hz": 2048.0,
                "justification": "Decode keyfob",
                "expected_effect": "Bit array",
            },
        )
        assert cmd.action == CommandAction.DECODE_MANCHESTER
        assert cmd.args["symbol_rate_hz"] == 2048.0
        assert cmd.args["polarity"] == "ieee"

    def test_decode_pwm_requires_both_widths(self) -> None:
        with pytest.raises(Exception):
            dispatch(
                "hackrf_decode_pwm",
                {
                    "iq_path": "/tmp/x.iq",
                    "short_us": 400,
                    "justification": "x",
                    "expected_effect": "y",
                },
            )

    def test_decode_pwm_rejects_short_ge_long(self) -> None:
        with pytest.raises(Exception):
            dispatch(
                "hackrf_decode_pwm",
                {
                    "iq_path": "/tmp/x.iq",
                    "short_us": 800,
                    "long_us": 400,
                    "justification": "x",
                    "expected_effect": "y",
                },
            )

    def test_decode_ppm(self) -> None:
        cmd = dispatch(
            "hackrf_decode_ppm",
            {
                "iq_path": "/tmp/x.iq",
                "pulse_us": 400.0,
                "justification": "x",
                "expected_effect": "y",
            },
        )
        assert cmd.action == CommandAction.DECODE_PPM
        assert cmd.args["pulse_us"] == 400.0

    def test_decode_nrz_variant_nrzi(self) -> None:
        cmd = dispatch(
            "hackrf_decode_nrz",
            {
                "iq_path": "/tmp/x.iq",
                "symbol_rate_hz": 9600.0,
                "variant": "nrzi",
                "justification": "x",
                "expected_effect": "y",
            },
        )
        assert cmd.action == CommandAction.DECODE_NRZ
        assert cmd.args["variant"] == "nrzi"

    def test_decode_pocsag(self) -> None:
        cmd = dispatch(
            "hackrf_decode_pocsag",
            {
                "iq_path": "/tmp/x.iq",
                "sample_rate_hz": 1_200_000,
                "baud": 1200,
                "justification": "Decode paging traffic",
                "expected_effect": "Per-message ric + payloads",
            },
        )
        assert cmd.action == CommandAction.DECODE_POCSAG
        assert cmd.args["baud"] == 1200

    def test_decode_pocsag_rejects_bad_baud(self) -> None:
        with pytest.raises(Exception):
            dispatch(
                "hackrf_decode_pocsag",
                {
                    "iq_path": "/tmp/x.iq",
                    "baud": 999,
                    "justification": "x",
                    "expected_effect": "y",
                },
            )

    def test_decode_ads_b(self) -> None:
        cmd = dispatch(
            "hackrf_decode_ads_b",
            {
                "iq_path": "/tmp/x.iq",
                "sample_rate_hz": 2_000_000,
                "justification": "Decode ADS-B",
                "expected_effect": "Aircraft frames",
            },
        )
        assert cmd.action == CommandAction.DECODE_ADS_B
        assert cmd.args["sample_rate_hz"] == 2_000_000

    def test_decode_ads_b_rejects_low_sample_rate(self) -> None:
        with pytest.raises(Exception):
            dispatch(
                "hackrf_decode_ads_b",
                {
                    "iq_path": "/tmp/x.iq",
                    "sample_rate_hz": 1_000_000,
                    "justification": "x",
                    "expected_effect": "y",
                },
            )

    def test_decode_nrz_rejects_bad_variant(self) -> None:
        with pytest.raises(Exception):
            dispatch(
                "hackrf_decode_nrz",
                {
                    "iq_path": "/tmp/x.iq",
                    "symbol_rate_hz": 9600.0,
                    "variant": "not-a-thing",
                    "justification": "x",
                    "expected_effect": "y",
                },
            )


class TestKnowledgeDispatch:
    """Dispatch surface for the knowledge tier — every verb round-trips."""

    def test_list_topics(self) -> None:
        cmd = dispatch(
            "hackrf_knowledge_list_topics",
            {
                "justification": "Orient the operator in the corpus",
                "expected_effect": "List of topic dirs and their files",
            },
        )
        assert cmd.action == CommandAction.KNOWLEDGE_LIST_TOPICS
        assert cmd.args == {}

    def test_read(self) -> None:
        cmd = dispatch(
            "hackrf_knowledge_read",
            {
                "topic": "dsp",
                "name": "reference.md",
                "justification": "Pull DSP reference",
                "expected_effect": "Return dsp/reference.md contents",
            },
        )
        assert cmd.action == CommandAction.KNOWLEDGE_READ
        assert cmd.args == {"topic": "dsp", "name": "reference.md"}

    def test_search(self) -> None:
        cmd = dispatch(
            "hackrf_knowledge_search",
            {
                "query": "Manchester",
                "justification": "Find Manchester references",
                "expected_effect": "List of matching lines",
            },
        )
        assert cmd.action == CommandAction.KNOWLEDGE_SEARCH
        assert cmd.args["query"] == "Manchester"
        assert cmd.args["max_results"] == 20  # default

    def test_lookup_band(self) -> None:
        cmd = dispatch(
            "hackrf_knowledge_lookup_band",
            {
                "freq_hz": 433_920_000,
                "justification": "Identify the ISM 433 band",
                "expected_effect": "Band record with blocked_tx flag",
            },
        )
        assert cmd.action == CommandAction.KNOWLEDGE_LOOKUP_BAND
        assert cmd.args["freq_hz"] == 433_920_000

    def test_lookup_modulation(self) -> None:
        cmd = dispatch(
            "hackrf_knowledge_lookup_modulation",
            {
                "name": "GFSK",
                "justification": "Look up GFSK demod pipeline",
                "expected_effect": "modulations.json record",
            },
        )
        assert cmd.action == CommandAction.KNOWLEDGE_LOOKUP_MODULATION
        assert cmd.args["name"] == "GFSK"

    def test_verify_claim(self) -> None:
        cmd = dispatch(
            "hackrf_knowledge_verify_claim",
            {
                "text": "The HackRF is full-duplex",
                "justification": "Sanity-check a claim",
                "expected_effect": "verdict + citation",
            },
        )
        assert cmd.action == CommandAction.KNOWLEDGE_VERIFY_CLAIM
        assert cmd.args["text"] == "The HackRF is full-duplex"

    def test_read_rejects_missing_topic(self) -> None:
        with pytest.raises(Exception):
            dispatch(
                "hackrf_knowledge_read",
                {
                    "name": "reference.md",
                    "justification": "x",
                    "expected_effect": "y",
                },
            )
