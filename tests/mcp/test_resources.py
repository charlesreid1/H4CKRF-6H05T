"""Unit tests for MCP resources."""

from __future__ import annotations

import json

import pytest

from hackrf_agent.mcp.resources import list_resources
from hackrf_agent.mcp.serialization import command_result_to_content, error_to_content
from hackrf_agent.domain.models import CommandAction, CommandResult


class TestResourceList:
    def test_list_includes_expected_uris(self) -> None:
        resources = list_resources("test-session-123")
        uris = {r.uri for r in resources}
        assert "hackrf://audit/recent?limit=50" in uris
        assert "hackrf://audit/session/test-session-123" in uris
        assert "hackrf://grants/active" in uris
        assert "hackrf://grants/all" in uris
        assert "hackrf://sessions/current" in uris

    def test_all_resources_have_mime_type(self) -> None:
        for r in list_resources("x"):
            assert r.mime_type == "application/json"


class TestSerialization:
    def test_success_result_produces_text_blocks(self) -> None:
        result = CommandResult(
            success=True,
            action=CommandAction.GET_DEVICE_INFO,
            message="Completed get_device_info.",
            data={"serial": "abc123"},
        )
        blocks = command_result_to_content(result, "s1")
        assert len(blocks) >= 1
        assert "succeeded" in blocks[0].text
        assert "s1" in blocks[0].text

    def test_failed_result_produces_error_text(self) -> None:
        result = CommandResult(
            success=False,
            action=CommandAction.SWEEP_SPECTRUM,
            message="Hardware error.",
            error="HackrfError: device not found",
        )
        blocks = command_result_to_content(result, "s2")
        assert "failed" in blocks[0].text
        assert "HackrfError" in blocks[0].text

    def test_result_with_data_includes_json_block(self) -> None:
        result = CommandResult(
            success=True,
            action=CommandAction.SWEEP_SPECTRUM,
            message="ok",
            data={"peaks": [{"freq_hz": 433.0e6, "power_dbfs": -20.0}]},
        )
        blocks = command_result_to_content(result, "s3")
        # Should have at least 2 blocks: summary + JSON data.
        assert len(blocks) >= 2
        # The JSON block should be parseable.
        parsed = json.loads(blocks[1].text)
        assert "peaks" in parsed

    def test_error_to_content(self) -> None:
        blocks = error_to_content(
            action="hackrf_transmit_iq",
            error="approval required",
            session_id="s4",
        )
        assert len(blocks) == 1
        assert "failed" in blocks[0].text
        assert "approval required" in blocks[0].text
        assert "s4" in blocks[0].text
