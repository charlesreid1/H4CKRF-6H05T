"""In-process MCP client ↔ server approval flow tests.

Spins up the server against an injected fake driver and drives it with a
real ``mcp.client.ClientSession`` that provides an ``elicitation_callback``.
Verifies that MEDIUM/HIGH commands trigger elicitation and that
approve/deny/CONFIRM flows produce the expected outcomes.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams
from mcp.types import ElicitResult

from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.executor import CommandExecutor
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.result_formatter import ResultFormatter
from hackrf_agent.domain.risk_assessor import RiskAssessor
from hackrf_agent.domain.session import new_session
from hackrf_agent.mcp.approval_port import McpApprovalPort
from hackrf_agent.mcp.server import create_server, ServerDeps

from tests.support.fake_driver import FakeDriver


# ---------------------------------------------------------------------------
# Helper: run a client/server pair with an elicitation callback
# ---------------------------------------------------------------------------


async def _run_with_callback(
    server_deps: ServerDeps,
    elicitation_callback,
    test_fn,
) -> None:
    """Spin up server and client, run ``test_fn(session)``.

    The elicitation callback will be invoked when the server calls
    ``session.elicit()`` from inside ``McpApprovalPort.request()``.
    """
    server = create_server(server_deps)
    init_opts = server.create_initialization_options()

    async with create_client_server_memory_streams() as (client_streams, server_streams):
        client_read, client_write = client_streams
        server_read, server_write = server_streams

        server_task = asyncio.create_task(
            server.run(server_read, server_write, init_opts)
        )

        async with ClientSession(
            client_read,
            client_write,
            elicitation_callback=elicitation_callback,
        ) as session:
            await session.initialize()
            await test_fn(session)

        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# Shared deps builder
# ---------------------------------------------------------------------------


async def _make_deps(
    db_path: Path,
    session_paths,
    fake_driver: FakeDriver,
    *,
    auto_approve_medium: bool = False,
) -> ServerDeps:
    await ensure_schema(db_path)
    audit = AuditService(db_path)
    await audit.__aenter__()

    permissions = PermissionService(db_path)
    risk_assessor = RiskAssessor()

    executor = CommandExecutor(
        session_id=session_paths.session_id,
        risk_assessor=risk_assessor,
        permissions=permissions,
        audit=audit,
        driver=fake_driver,
        formatter=ResultFormatter(),
        approval=McpApprovalPort(auto_approve_medium=auto_approve_medium),
        session_paths=session_paths,
    )

    deps = ServerDeps(
        session_id=session_paths.session_id,
        session_paths=session_paths,
        driver=fake_driver,
        audit=audit,
        permissions=permissions,
        risk_assessor=risk_assessor,
        executor=executor,
        driver_lock=asyncio.Lock(),
        auto_approve_medium=auto_approve_medium,
    )
    deps._audit_ctx = audit  # type: ignore[attr-defined]
    return deps


# ---------------------------------------------------------------------------
# Elicitation callback helpers
# ---------------------------------------------------------------------------


def _make_callback(action: str, content: dict) -> callable:
    """Return an elicitation callback that always replies with the given result."""
    async def _cb(context, params) -> ElicitResult:
        return ElicitResult(action=action, content=content)
    return _cb


def _make_approve_callback(confirm: str | None = None) -> callable:
    """Return a callback that approves the command."""
    content = {"approve": True}
    if confirm is not None:
        content["confirm"] = confirm
    return _make_callback("accept", content)


def _make_deny_callback() -> callable:
    """Return a callback that denies the command."""
    return _make_callback("accept", {"approve": False})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMediumApprovalFlow:
    """MEDIUM-risk commands trigger elicitation and respect the response."""

    async def test_medium_approved(
        self, tmp_path: Path, fake_driver: FakeDriver
    ) -> None:
        db_path = tmp_path / "agent.db"
        session_paths = new_session(tmp_path / "sessions")
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:
            elicitation_called = []

            async def _cb(context, params) -> ElicitResult:
                elicitation_called.append(params)
                return ElicitResult(
                    action="accept", content={"approve": True}
                )

            async def _test(session: ClientSession) -> None:
                # dwell_s=5.0 → MEDIUM risk (long sweep)
                result = await session.call_tool(
                    "hackrf_sweep_spectrum",
                    {
                        "start_freq_hz": 433_000_000,
                        "end_freq_hz": 434_000_000,
                        "dwell_s": 5.0,
                        "justification": "test medium approval",
                        "expected_effect": "sweep with dwell > 2s",
                    },
                )
                assert result.is_error is False
                text = "".join(
                    b.text for b in result.content if hasattr(b, "text")
                )
                assert "succeeded" in text

            await _run_with_callback(deps, _cb, _test)

            # Elicitation should have been called exactly once.
            assert len(elicitation_called) == 1
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]

    async def test_medium_denied(
        self, tmp_path: Path, fake_driver: FakeDriver
    ) -> None:
        db_path = tmp_path / "agent.db"
        session_paths = new_session(tmp_path / "sessions")
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:
            async def _cb(context, params) -> ElicitResult:
                return ElicitResult(
                    action="accept", content={"approve": False}
                )

            async def _test(session: ClientSession) -> None:
                result = await session.call_tool(
                    "hackrf_sweep_spectrum",
                    {
                        "start_freq_hz": 433_000_000,
                        "end_freq_hz": 434_000_000,
                        "dwell_s": 5.0,
                        "justification": "test deny",
                        "expected_effect": "should be denied",
                    },
                )
                assert result.is_error is True
                text = "".join(
                    b.text for b in result.content if hasattr(b, "text")
                )
                assert "denied" in text.lower() or "approval" in text.lower()

            await _run_with_callback(deps, _cb, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]

    async def test_medium_elicitation_declined(
        self, tmp_path: Path, fake_driver: FakeDriver
    ) -> None:
        """When the user declines the elicitation action (not content), deny."""
        db_path = tmp_path / "agent.db"
        session_paths = new_session(tmp_path / "sessions")
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:
            async def _cb(context, params) -> ElicitResult:
                return ElicitResult(action="decline", content={})

            async def _test(session: ClientSession) -> None:
                result = await session.call_tool(
                    "hackrf_sweep_spectrum",
                    {
                        "start_freq_hz": 433_000_000,
                        "end_freq_hz": 434_000_000,
                        "dwell_s": 5.0,
                        "justification": "test decline",
                        "expected_effect": "should be declined",
                    },
                )
                assert result.is_error is True

            await _run_with_callback(deps, _cb, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]

    async def test_medium_auto_approve_skips_elicitation(
        self, tmp_path: Path, fake_driver: FakeDriver
    ) -> None:
        db_path = tmp_path / "agent.db"
        session_paths = new_session(tmp_path / "sessions")
        deps = await _make_deps(
            db_path, session_paths, fake_driver, auto_approve_medium=True,
        )
        try:
            elicitation_called = []

            async def _cb(context, params) -> ElicitResult:
                elicitation_called.append(1)
                return ElicitResult(action="accept", content={"approve": True})

            async def _test(session: ClientSession) -> None:
                result = await session.call_tool(
                    "hackrf_sweep_spectrum",
                    {
                        "start_freq_hz": 433_000_000,
                        "end_freq_hz": 434_000_000,
                        "dwell_s": 5.0,
                        "justification": "auto approve test",
                        "expected_effect": "should auto-approve",
                    },
                )
                assert result.is_error is False

            await _run_with_callback(deps, _cb, _test)

            # Elicitation should NOT have been called (auto-approved).
            assert len(elicitation_called) == 0
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]


class TestHighApprovalFlow:
    """HIGH-risk commands require CONFIRM string."""

    async def test_high_approved_with_confirm(
        self, tmp_path: Path, fake_driver: FakeDriver
    ) -> None:
        db_path = tmp_path / "agent.db"
        session_paths = new_session(tmp_path / "sessions")
        # Create a dummy IQ file inside the session dir so the handler
        # accepts the path.
        iq_file = session_paths.iq_dir / "test.iq"
        iq_file.parent.mkdir(parents=True, exist_ok=True)
        iq_file.write_bytes(b"\x00\x00" * 1024)

        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:
            async def _cb(context, params) -> ElicitResult:
                return ElicitResult(
                    action="accept",
                    content={"approve": True, "confirm": "CONFIRM"},
                )

            async def _test(session: ClientSession) -> None:
                # 144 MHz = amateur 2m band → HIGH risk
                result = await session.call_tool(
                    "hackrf_transmit_iq",
                    {
                        "center_freq_hz": 144_000_000,
                        "iq_path": str(iq_file),
                        "tx_vga_gain_db": 10,
                        "justification": "test high approval",
                        "expected_effect": "TX in amateur band",
                    },
                )
                assert result.is_error is False
                text = "".join(
                    b.text for b in result.content if hasattr(b, "text")
                )
                assert "succeeded" in text

            await _run_with_callback(deps, _cb, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]

    async def test_high_denied_with_wrong_confirm(
        self, tmp_path: Path, fake_driver: FakeDriver
    ) -> None:
        db_path = tmp_path / "agent.db"
        session_paths = new_session(tmp_path / "sessions")
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:
            async def _cb(context, params) -> ElicitResult:
                return ElicitResult(
                    action="accept",
                    content={"approve": True, "confirm": "nope"},
                )

            async def _test(session: ClientSession) -> None:
                result = await session.call_tool(
                    "hackrf_transmit_iq",
                    {
                        "center_freq_hz": 144_000_000,
                        "iq_path": str(tmp_path / "test.iq"),
                        "tx_vga_gain_db": 10,
                        "justification": "test wrong confirm",
                        "expected_effect": "should be denied",
                    },
                )
                assert result.is_error is True

            await _run_with_callback(deps, _cb, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]

    async def test_high_denied_missing_confirm(
        self, tmp_path: Path, fake_driver: FakeDriver
    ) -> None:
        """HIGH command where callback doesn't include confirm at all."""
        db_path = tmp_path / "agent.db"
        session_paths = new_session(tmp_path / "sessions")
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:
            async def _cb(context, params) -> ElicitResult:
                return ElicitResult(
                    action="accept",
                    content={"approve": True},  # no "confirm" key
                )

            async def _test(session: ClientSession) -> None:
                result = await session.call_tool(
                    "hackrf_transmit_iq",
                    {
                        "center_freq_hz": 144_000_000,
                        "iq_path": str(tmp_path / "test.iq"),
                        "tx_vga_gain_db": 10,
                        "justification": "test missing confirm",
                        "expected_effect": "should be denied",
                    },
                )
                assert result.is_error is True

            await _run_with_callback(deps, _cb, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]
