"""Convert domain objects to MCP wire-format content blocks.

The MCP host receives tool results as a list of content blocks (text,
image, embedded resource). This module converts ``CommandResult`` and
related domain objects into ``TextContent`` blocks suitable for
``CallToolResult.content``.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.types import TextContent

from hackrf_agent.domain.models import CommandResult


def command_result_to_content(
    result: CommandResult,
    session_id: str,
) -> list[TextContent]:
    """Convert a ``CommandResult`` into one or more ``TextContent`` blocks.

    The primary block is a human-readable summary. If the result carries
    structured ``data``, it is included as a JSON block so hosts can
    parse it programmatically.
    """
    blocks: list[TextContent] = []

    # Primary text block — human-readable summary.
    status = "✓ succeeded" if result.success else "✗ failed"
    lines = [
        f"{status} — {result.action.value}",
        f"session: {session_id}",
    ]
    if result.message:
        lines.append(f"message: {result.message}")
    if result.error:
        lines.append(f"error: {result.error}")
    blocks.append(TextContent(type="text", text="\n".join(lines)))

    # Structured data block (if present).
    if result.data:
        blocks.append(
            TextContent(
                type="text",
                text=json.dumps(result.data, indent=2, default=str),
            )
        )

    return blocks


def error_to_content(
    action: str,
    error: str,
    session_id: str,
) -> list[TextContent]:
    """Build an error tool result for when a tool call fails before execution."""
    return [
        TextContent(
            type="text",
            text=(
                f"✗ failed — {action}\n"
                f"session: {session_id}\n"
                f"error: {error}"
            ),
        )
    ]
