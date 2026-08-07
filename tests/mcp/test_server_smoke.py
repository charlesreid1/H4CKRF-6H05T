"""In-process MCP client ↔ server smoke test.

Spins up the server against an injected fake HackRF driver and drives it
with a real ``mcp.client.ClientSession`` over memory streams. This test
would have caught every SDK-shape bug in the original implementation.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.executor import CommandExecutor
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.result_formatter import ResultFormatter
from hackrf_agent.domain.risk_assessor import RiskAssessor
from hackrf_agent.domain.session import new_session
from hackrf_agent.mcp.approval_port import McpApprovalPort
from hackrf_agent.mcp.server import ServerDeps, create_server
from tests.support.fake_driver import FakeDriver

# ---------------------------------------------------------------------------
# Helper: run a client/server pair over memory streams in the test's own task
# ---------------------------------------------------------------------------


async def _run_with_client(
    server_deps: ServerDeps,
    test_fn,
) -> None:
    """Spin up the server, connect a client, and call ``test_fn(session)``.

    Everything — server, client, and test body — runs in a single task so
    ``ClientSession``'s internal ``anyio`` task group doesn't cross tasks.
    """
    server = create_server(server_deps)
    init_opts = server.create_initialization_options()

    async with create_client_server_memory_streams() as (client_streams, server_streams):
        client_read, client_write = client_streams
        server_read, server_write = server_streams

        server_task = asyncio.create_task(
            server.run(server_read, server_write, init_opts)
        )

        async with ClientSession(client_read, client_write) as session:
            await session.initialize()
            await test_fn(session)

        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# Fixtures (sync deps only; async deps are pulled inside helpers)
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "agent.db"


@pytest.fixture
def session_paths(tmp_path: Path):
    return new_session(tmp_path / "sessions")


@pytest.fixture
def fake_driver() -> FakeDriver:
    return FakeDriver()


async def _make_deps(
    db_path: Path,
    session_paths,
    fake_driver: FakeDriver,
) -> ServerDeps:
    """Build ServerDeps with a real DB + fake driver."""
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
        approval=McpApprovalPort(auto_approve_medium=False),
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
        auto_approve_medium=False,
    )

    # Attach audit for cleanup.
    deps._audit_ctx = audit  # type: ignore[attr-defined]
    return deps


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListTools:
    async def test_lists_all_command_action_tools(
        self, db_path: Path, session_paths, fake_driver: FakeDriver
    ) -> None:
        from hackrf_agent.domain.models import CommandAction

        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:

            async def _test(session: ClientSession) -> None:
                result = await session.list_tools()
                tool_names = [t.name for t in result.tools]
                # One MCP tool per CommandAction, prefixed hackrf_.
                assert len(tool_names) == len(list(CommandAction))
                for name in tool_names:
                    assert name.startswith("hackrf_"), f"Bad tool name: {name}"

            await _run_with_client(deps, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]

    async def test_get_device_info_tool_exists(
        self, db_path: Path, session_paths, fake_driver: FakeDriver
    ) -> None:
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:

            async def _test(session: ClientSession) -> None:
                result = await session.list_tools()
                names = {t.name for t in result.tools}
                assert "hackrf_get_device_info" in names

            await _run_with_client(deps, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]


class TestCallTool:
    async def test_get_device_info_returns_fake_serial(
        self, db_path: Path, session_paths, fake_driver: FakeDriver
    ) -> None:
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:

            async def _test(session: ClientSession) -> None:
                result = await session.call_tool(
                    "hackrf_get_device_info",
                    {
                        "justification": "smoke test",
                        "expected_effect": "identify fake device",
                    },
                )
                assert result.is_error is False
                text = "".join(
                    b.text for b in result.content if hasattr(b, "text")
                )
                assert "fake-serial" in text

            await _run_with_client(deps, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]

    async def test_bad_arguments_returns_error(
        self, db_path: Path, session_paths, fake_driver: FakeDriver
    ) -> None:
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:

            async def _test(session: ClientSession) -> None:
                # Missing required field "start_freq_hz" for sweep_spectrum.
                result = await session.call_tool(
                    "hackrf_sweep_spectrum",
                    {
                        "justification": "test",
                        "expected_effect": "test",
                    },
                )
                assert result.is_error is True

            await _run_with_client(deps, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]

    async def test_unknown_tool_returns_error(
        self, db_path: Path, session_paths, fake_driver: FakeDriver
    ) -> None:
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:

            async def _test(session: ClientSession) -> None:
                result = await session.call_tool(
                    "hackrf_nonexistent",
                    {"justification": "x", "expected_effect": "y"},
                )
                assert result.is_error is True

            await _run_with_client(deps, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]

    async def test_grant_list_works(
        self, db_path: Path, session_paths, fake_driver: FakeDriver
    ) -> None:
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:

            async def _test(session: ClientSession) -> None:
                result = await session.call_tool(
                    "hackrf_grant_list",
                    {
                        "justification": "check grants",
                        "expected_effect": "list grants",
                    },
                )
                assert result.is_error is False

            await _run_with_client(deps, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]


class TestResources:
    async def test_list_resources(
        self, db_path: Path, session_paths, fake_driver: FakeDriver
    ) -> None:
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:

            async def _test(session: ClientSession) -> None:
                result = await session.list_resources()
                uris = {r.uri for r in result.resources}
                assert "hackrf://audit/recent?limit=50" in uris
                assert "hackrf://grants/active" in uris
                assert "hackrf://sessions/current" in uris

            await _run_with_client(deps, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]

    async def test_read_sessions_current(
        self, db_path: Path, session_paths, fake_driver: FakeDriver
    ) -> None:
        deps = await _make_deps(db_path, session_paths, fake_driver)
        try:

            async def _test(session: ClientSession) -> None:
                result = await session.read_resource("hackrf://sessions/current")
                assert len(result.contents) >= 1
                data = json.loads(result.contents[0].text)
                assert "session_id" in data
                assert "root" in data

            await _run_with_client(deps, _test)
        finally:
            await deps._audit_ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]
