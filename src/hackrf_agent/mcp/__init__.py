"""MCP server package for HackRF agent.

Exposes the same safety-gated command surface as the chat CLI,
but as a Model Context Protocol server so any MCP-aware host
can drive the radio.
"""

from hackrf_agent.mcp.server import create_server, run_server, ServerDeps

__all__ = ["create_server", "run_server", "ServerDeps"]
