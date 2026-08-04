"""``hackrf-agent mcp`` — thin Typer command that execs the MCP server.

This is a convenience alias so ``hackrf-agent mcp`` and ``hackrf-agent-mcp``
both work. Hosts that want a single-binary config can point at the former.
"""

from __future__ import annotations

import asyncio
import sys

import typer


def mcp() -> None:
    """Start the HackRF MCP server on stdio.

    The server exposes HackRF One control as MCP tools, resources, and
    elicitation requests. It speaks the MCP wire protocol over stdin/stdout;
    all logging goes to stderr.
    """
    from hackrf_agent.mcp.server import run_server

    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback

        traceback.print_exc(file=sys.stderr)
        raise typer.Exit(code=1)
