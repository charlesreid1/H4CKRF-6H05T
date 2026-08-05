"""``python -m hackrf_agent.mcp`` and ``hackrf-agent-mcp`` console-script entry point."""

from __future__ import annotations

import asyncio
import sys

from hackrf_agent.mcp.server import run_server


def main() -> None:
    """Entry point for ``hackrf-agent-mcp`` console script."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
