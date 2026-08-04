"""Route all Python logging to stderr.

The MCP wire protocol uses stdout for JSON framing. Anything written to
stdout corrupts the stream, so every handler, dependency, and third-party
library MUST only emit via stderr.

This module configures the root logger with a StreamHandler targeting
``sys.stderr``. Import it early (before any other imports that might log).
"""

from __future__ import annotations

import logging
import os
import sys


def configure(level: int | str | None = None) -> None:
    """Route all Python logging to stderr at *level*.

    Args:
        level: Log level. Defaults to ``INFO``, or ``DEBUG`` when
               ``HACKRF_MCP_LOG_LEVEL=DEBUG`` is set in the environment.
    """
    if level is None:
        env_level = os.environ.get("HACKRF_MCP_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any pre-existing stdout handlers.
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(handler)

    # Belt-and-suspenders: forbid the root logger from using stdout.
    root.propagate = False

    # Also capture warnings through the logging system.
    logging.captureWarnings(True)
