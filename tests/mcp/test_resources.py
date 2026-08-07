"""Unit tests for MCP resources."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.audit_service import AuditService, make_event, new_trace_id
from hackrf_agent.domain.models import (
    AuditEventType,
    CommandAction,
    CommandResult,
    RiskLevel,
)
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.session import new_session
from hackrf_agent.mcp.resources import list_resources, read_resource
from hackrf_agent.mcp.serialization import command_result_to_content, error_to_content


class TestResourceList:
    def test_list_includes_expected_uris(self) -> None:
        resources = list_resources("test-session-123")
        uris = {r.uri for r in resources}
        assert "hackrf://audit/recent?limit=50" in uris
        assert "hackrf://audit/session/test-session-123" in uris
        assert "hackrf://grants/active" in uris
        assert "hackrf://grants/all" in uris
        assert "hackrf://sessions/current" in uris
        assert "hackrf://sessions/test-session-123/events" in uris

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

class TestSessionEventsResource:
    """hackrf://sessions/<id>/events reads from the audit log."""

    async def test_events_uri_returns_audit_rows(self, tmp_path: Path) -> None:
        db = tmp_path / "audit.db"
        await ensure_schema(db)
        perms = PermissionService(db)
        session_paths = new_session(tmp_path / "sessions")

        async with AuditService(db) as audit:
            # Seed a couple of events under session "s-events".
            trace = new_trace_id()
            await audit.log(
                make_event(
                    trace_id=trace,
                    session_id="s-events",
                    event=AuditEventType.COMMAND_RECEIVED,
                    action=CommandAction.GET_DEVICE_INFO,
                )
            )
            await audit.log(
                make_event(
                    trace_id=trace,
                    session_id="s-events",
                    event=AuditEventType.EXECUTED,
                    action=CommandAction.GET_DEVICE_INFO,
                    risk_level=RiskLevel.LOW,
                )
            )
            # Also seed one under a different session to confirm filtering.
            await audit.log(
                make_event(
                    trace_id=new_trace_id(),
                    session_id="other-session",
                    event=AuditEventType.COMMAND_RECEIVED,
                    action=CommandAction.GRANT_LIST,
                )
            )

            # Yield to let the async audit writer drain the queue.
            await asyncio.sleep(0.05)

            result = await read_resource(
                "hackrf://sessions/s-events/events",
                audit=audit,
                permissions=perms,
                session_paths=session_paths,
                session_id="s-events",
            )
        assert result is not None
        text = result.contents[0].text
        parsed = json.loads(text)
        assert isinstance(parsed, list)
        session_ids = {row["session_id"] for row in parsed}
        assert session_ids == {"s-events"}
        events = [row["event"] for row in parsed]
        assert "COMMAND_RECEIVED" in events
        assert "EXECUTED" in events

    async def test_events_uri_respects_limit_query(
        self, tmp_path: Path
    ) -> None:
        db = tmp_path / "audit.db"
        await ensure_schema(db)
        perms = PermissionService(db)
        session_paths = new_session(tmp_path / "sessions")

        async with AuditService(db) as audit:
            for _ in range(5):
                await audit.log(
                    make_event(
                        trace_id=new_trace_id(),
                        session_id="s-limit",
                        event=AuditEventType.COMMAND_RECEIVED,
                        action=CommandAction.GET_DEVICE_INFO,
                    )
                )
            # Yield to let the async audit writer drain the queue.
            await asyncio.sleep(0.05)

            result = await read_resource(
                "hackrf://sessions/s-limit/events?limit=2",
                audit=audit,
                permissions=perms,
                session_paths=session_paths,
                session_id="s-limit",
            )
        assert result is not None
        parsed = json.loads(result.contents[0].text)
        assert len(parsed) == 2


class TestErrorContent:
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
