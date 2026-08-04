"""Top-level MCP server: build, register handlers, run stdio.

This module creates the MCP ``Server`` using the real ``mcp`` SDK v2.0.0
API (handlers passed as constructor kwargs), wires a ``McpApprovalPort``
via a ``ContextVar``, and provides ``run_server()`` as the process entry
point for the ``hackrf-agent-mcp`` binary.

Tests can call ``create_server()`` directly with injected dependencies
to spin up an in-process server without touching real hardware.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from dataclasses import dataclass
from typing import Any

from mcp.server import Server
from mcp.server.context import ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListResourcesResult,
    ListToolsResult,
)

from hackrf_agent.cli.settings import SettingsService
from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.executor import CommandExecutor
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.result_formatter import ResultFormatter
from hackrf_agent.domain.risk_assessor import RiskAssessor
from hackrf_agent.domain.session import new_session, SessionPaths
from hackrf_agent.domain.handlers import DriverProtocol

from hackrf_agent.mcp.approval_port import McpApprovalPort, _current_session
from hackrf_agent.mcp.logging_config import configure as configure_logging
from hackrf_agent.mcp.resources import list_resources as build_resource_list
from hackrf_agent.mcp.resources import read_resource as read_resource_uri
from hackrf_agent.mcp.serialization import command_result_to_content, error_to_content
from hackrf_agent.mcp.tool_registry import dispatch, list_tools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependency bag — everything the server handlers need
# ---------------------------------------------------------------------------


@dataclass
class ServerDeps:
    """Dependencies injected into the MCP server handlers.

    Tests populate this with fakes; ``run_server()`` populates it with
    real services + a real HackRF driver.
    """

    session_id: str
    session_paths: SessionPaths
    driver: DriverProtocol
    audit: AuditService
    permissions: PermissionService
    risk_assessor: RiskAssessor
    executor: CommandExecutor
    driver_lock: asyncio.Lock
    auto_approve_medium: bool = False
    # Mutable — set by the tool-call handler so SIGINT can cancel the
    # currently-running tool.
    current_tool_task: asyncio.Task[Any] | None = None


# ---------------------------------------------------------------------------
# Server factory — testable entry point
# ---------------------------------------------------------------------------


def create_server(deps: ServerDeps) -> Server:
    """Build and return a configured MCP ``Server``.

    Handlers are passed as keyword arguments to ``Server()`` — the v2.0.0
    SDK API. Each handler closes over *deps*.

    The returned server is ready to run via
    ``server.run(read_stream, write_stream, init_opts)``.
    """
    session_id = deps.session_id
    session_paths = deps.session_paths
    audit = deps.audit
    permissions = deps.permissions
    executor = deps.executor
    driver_lock = deps.driver_lock

    # ------------------------------------------------------------------
    # tools/list
    # ------------------------------------------------------------------
    async def _list_tools(
        ctx: ServerRequestContext,
        params: object | None,
    ) -> ListToolsResult:
        tools = list_tools()
        return ListToolsResult(tools=tools)

    # ------------------------------------------------------------------
    # tools/call
    # ------------------------------------------------------------------
    async def _call_tool(
        ctx: ServerRequestContext,
        params: CallToolRequestParams,
    ) -> CallToolResult:
        # Wire the session into the ContextVar so McpApprovalPort
        # can call session.elicit() if needed.
        _current_session.set(ctx.session)

        try:
            command = dispatch(params.name, params.arguments or {})
        except Exception as exc:
            logger.exception("Failed to parse tool call %s", params.name)
            return CallToolResult(
                content=error_to_content(
                    action=params.name,
                    error=f"Bad arguments: {exc}",
                    session_id=session_id,
                ),
                is_error=True,
            )

        # Track this task so the SIGINT handler can cancel it.
        deps.current_tool_task = asyncio.current_task()  # type: ignore[assignment]
        try:
            # Serialize on the driver lock (USB is exclusive).
            async with driver_lock:
                result = await executor.execute(command)
        finally:
            deps.current_tool_task = None

        return CallToolResult(
            content=command_result_to_content(result, session_id=session_id),
            is_error=not result.success,
        )

    # ------------------------------------------------------------------
    # resources/list
    # ------------------------------------------------------------------
    async def _list_resources(
        ctx: ServerRequestContext,
        params: object | None,
    ) -> ListResourcesResult:
        resources = build_resource_list(session_id)
        return ListResourcesResult(resources=resources)

    # ------------------------------------------------------------------
    # resources/read
    # ------------------------------------------------------------------
    async def _read_resource(
        ctx: ServerRequestContext,
        params: Any,
    ) -> Any:
        from mcp.types import ReadResourceRequestParams

        if not isinstance(params, ReadResourceRequestParams):
            raise ValueError(
                f"Expected ReadResourceRequestParams, got {type(params)}"
            )

        result = await read_resource_uri(
            str(params.uri),
            audit=audit,
            permissions=permissions,
            session_paths=session_paths,
            session_id=session_id,
        )
        if result is None:
            raise ValueError(f"Unknown resource: {params.uri}")
        return result

    # Build the server with handlers wired via constructor kwargs.
    return Server(
        name="hackrf-agent-mcp",
        version="0.1.0",
        description="Safety-gated HackRF One control via MCP",
        on_list_tools=_list_tools,
        on_call_tool=_call_tool,
        on_list_resources=_list_resources,
        on_read_resource=_read_resource,
    )


# ---------------------------------------------------------------------------
# stdio runner — the process entry point
# ---------------------------------------------------------------------------


async def run_server() -> None:
    """Set up domain dependencies, build the server, and run on stdio.

    This is the top-level entry point for the ``hackrf-agent-mcp``
    binary. It never returns until the host closes the connection
    or the process receives a terminal signal.
    """
    configure_logging()
    logger.info("hackrf-agent-mcp starting (mcp SDK v2.0.0)")

    # Resolve home directory.
    settings_svc = SettingsService()
    home_dir = settings_svc.home_dir
    db_path = settings_svc.db_path
    sessions_dir = settings_svc.sessions_dir

    home_dir.mkdir(parents=True, exist_ok=True)
    await ensure_schema(db_path)

    # Create session (one per server process — matches MCP lifecycle).
    session_paths = new_session(sessions_dir)
    session_id = session_paths.session_id
    logger.info("Session %s — root=%s", session_id, session_paths.root)

    # Read auto-approve from settings.
    loaded = settings_svc.load()
    auto_approve_medium = loaded.auto_approve_medium

    # Lazy import — avoid pyhackrf import until we're actually running.
    from hackrf_agent.hw.hackrf_driver import HackrfDriver

    # Driver lock — serialize all tool calls (USB is exclusive).
    driver_lock = asyncio.Lock()

    stop_event = asyncio.Event()
    permissions = PermissionService(db_path)
    risk_assessor = RiskAssessor()

    # Signal handling: first SIGINT cancels the current tool call + sets
    # stop_event; second SIGINT exits. SIGTERM behaves like second SIGINT.
    # deps_container[0] is set after ServerDeps is created below.
    sigint_count = 0
    deps_container: list[ServerDeps | None] = [None]

    def _on_signal(sig: signal.Signals) -> None:
        nonlocal sigint_count
        if sig == signal.SIGINT:
            sigint_count += 1
            if sigint_count == 1:
                logger.warning("SIGINT — aborting current tool call")
                stop_event.set()
                deps = deps_container[0]
                task = deps.current_tool_task if deps else None
                if task is not None and not task.done():
                    task.cancel()
            else:
                logger.warning("Second SIGINT — exiting")
                sys.exit(1)
        elif sig == signal.SIGTERM:
            logger.info("SIGTERM — shutting down")
            stop_event.set()
            deps = deps_container[0]
            task = deps.current_tool_task if deps else None
            if task is not None and not task.done():
                task.cancel()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, lambda: _on_signal(signal.SIGINT))
    loop.add_signal_handler(signal.SIGTERM, lambda: _on_signal(signal.SIGTERM))

    try:
        async with (
            AuditService(db_path) as audit,
            HackrfDriver(stop_event=stop_event) as driver,
        ):
            approval_port = McpApprovalPort(
                auto_approve_medium=auto_approve_medium,
            )

            executor = CommandExecutor(
                session_id=session_id,
                risk_assessor=risk_assessor,
                permissions=permissions,
                audit=audit,
                driver=driver,
                formatter=ResultFormatter(),
                approval=approval_port,
                session_paths=session_paths,
            )

            deps = ServerDeps(
                session_id=session_id,
                session_paths=session_paths,
                driver=driver,
                audit=audit,
                permissions=permissions,
                risk_assessor=risk_assessor,
                executor=executor,
                driver_lock=driver_lock,
                auto_approve_medium=auto_approve_medium,
            )
            deps_container[0] = deps

            server = create_server(deps)
            init_opts = server.create_initialization_options()

            logger.info("MCP server ready on stdio")
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, init_opts)

    finally:
        loop.remove_signal_handler(signal.SIGINT)
        loop.remove_signal_handler(signal.SIGTERM)
        logger.info("hackrf-agent-mcp shutdown complete")
