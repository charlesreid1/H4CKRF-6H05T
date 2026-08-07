"""Runs scripts/validate_knowledge_records.py as a unit test.

The pre-commit hook covers commits; this test covers every-push CI
so a regression in knowledge/records/*.json can't slip through a
commit that skipped the hook.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "validate_knowledge_records.py"


def test_records_validate_against_schemas() -> None:
    r = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (
        f"scripts/validate_knowledge_records.py reports errors:\n"
        f"stdout:\n{r.stdout}\n"
        f"stderr:\n{r.stderr}"
    )
