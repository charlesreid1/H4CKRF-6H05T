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
