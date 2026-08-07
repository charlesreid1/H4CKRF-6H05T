"""Doc freshness gates.

Every CommandAction must be enumerated in:

  - docs/execute_command_schema.md  (one ## section per action)
  - docs/mcp.md                     (one row in the tools table)

And the on-disk contents must match what
``scripts/generate_execute_command_schema.py`` would produce. Failing
this test usually means someone added a verb without regenerating.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from hackrf_agent.domain.models import CommandAction

REPO_ROOT = Path(__file__).parent.parent.parent
SCHEMA_MD = REPO_ROOT / "docs" / "execute_command_schema.md"
MCP_MD = REPO_ROOT / "docs" / "mcp.md"
GENERATOR = REPO_ROOT / "scripts" / "generate_execute_command_schema.py"


def test_execute_command_schema_lists_every_action() -> None:
    """docs/execute_command_schema.md has one ## `<action>` heading per CommandAction."""
    text = SCHEMA_MD.read_text(encoding="utf-8")
    for action in CommandAction:
        heading = f"## `{action.value}`"
        assert heading in text, (
            f"docs/execute_command_schema.md missing section for {action.value!r}. "
            f"Run `python scripts/generate_execute_command_schema.py` and commit."
        )


def test_mcp_tools_table_lists_every_action() -> None:
    """docs/mcp.md tools table has one row per CommandAction."""
    text = MCP_MD.read_text(encoding="utf-8")
    for action in CommandAction:
        needle = f"`hackrf_{action.value}`"
        assert needle in text, (
            f"docs/mcp.md missing tools-table row for {action.value!r}. "
            f"Run `python scripts/generate_execute_command_schema.py` and commit."
        )


def test_generator_check_passes() -> None:
    """`generate_execute_command_schema.py --check` exits 0 (no drift).

    This is the CI-style guardrail: if the code has changed but the
    committed docs/*.md and schemas/*.json don't reflect it, this test
    fails and points at the fix.
    """
    r = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (
        f"Generator --check reports drift:\n"
        f"stdout:\n{r.stdout}\n"
        f"stderr:\n{r.stderr}\n"
        f"Run `python scripts/generate_execute_command_schema.py` and commit."
    )
