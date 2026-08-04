"""Tests for scripts/generate_execute_command_schema.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from hackrf_agent.domain.models import CommandAction


def _regenerator_module():
    """Import the regenerator module, adding scripts/ to sys.path."""
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    mod = __import__("generate_execute_command_schema")
    sys.path.pop(0)
    return mod


# ---------------------------------------------------------------------------
# Test 1: Every CommandAction has a PER_ACTION_DOCS entry
# ---------------------------------------------------------------------------


def test_every_action_has_docs() -> None:
    """set(PER_ACTION_DOCS.keys()) == set(CommandAction)."""
    mod = _regenerator_module()
    missing = set(CommandAction) - set(mod.PER_ACTION_DOCS.keys())
    extra = set(mod.PER_ACTION_DOCS.keys()) - set(CommandAction)
    assert not missing, f"CommandAction members without docs: {missing}"
    assert not extra, f"PER_ACTION_DOCS entries without enum members: {extra}"


# ---------------------------------------------------------------------------
# Test 2: Running the script twice produces byte-identical output
# ---------------------------------------------------------------------------


def test_regenerator_is_deterministic(tmp_path: Path) -> None:
    """Two runs on the same code produce byte-identical files."""
    script = Path(__file__).parent.parent.parent / "scripts" / "generate_execute_command_schema.py"

    # First run.
    r1 = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert r1.returncode == 0, f"first run failed: {r1.stderr}"

    # Read the output files.
    md1 = (Path.cwd() / "docs" / "execute_command_schema.md").read_bytes()
    json1 = (Path.cwd() / "schemas" / "execute_command.schema.json").read_bytes()

    # Second run.
    r2 = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert r2.returncode == 0, f"second run failed: {r2.stderr}"

    md2 = (Path.cwd() / "docs" / "execute_command_schema.md").read_bytes()
    json2 = (Path.cwd() / "schemas" / "execute_command.schema.json").read_bytes()

    assert md1 == md2, "Markdown output is not deterministic"
    assert json1 == json2, "JSON output is not deterministic"


# ---------------------------------------------------------------------------
# Test 3: Generated Markdown has one section per CommandAction
# ---------------------------------------------------------------------------


def test_markdown_has_one_section_per_action() -> None:
    """Generated markdown contains one ## `action` section per CommandAction value."""
    md_path = Path(__file__).parent.parent.parent / "docs" / "execute_command_schema.md"
    text = md_path.read_text()

    for action in CommandAction:
        heading = f"## `{action.value}`"
        assert heading in text, f"Missing heading {heading!r} in execute_command_schema.md"


# ---------------------------------------------------------------------------
# Test 4: Generated JSON is valid and matches EXECUTE_COMMAND_TOOL_SCHEMA structure
# ---------------------------------------------------------------------------


def test_json_schema_is_valid_and_matches() -> None:
    """Generated JSON is valid Draft-07 schema with expected top-level keys."""
    from hackrf_agent.ai.prompts import EXECUTE_COMMAND_TOOL_SCHEMA

    json_path = Path(__file__).parent.parent.parent / "schemas" / "execute_command.schema.json"
    text = json_path.read_text()

    # Valid JSON.
    parsed = json.loads(text)
    assert isinstance(parsed, dict)

    # Top-level keys match the tool schema.
    assert parsed["name"] == EXECUTE_COMMAND_TOOL_SCHEMA["name"]
    assert parsed["description"] == EXECUTE_COMMAND_TOOL_SCHEMA["description"]
    assert "input_schema" in parsed
    assert parsed["input_schema"]["type"] == "object"


# ---------------------------------------------------------------------------
# Test 5: No drift — regenerator output matches committed files
# ---------------------------------------------------------------------------


def test_no_drift_between_code_and_reference() -> None:
    """Running the regenerator doesn't change the committed files (no drift)."""
    script = Path(__file__).parent.parent.parent / "scripts" / "generate_execute_command_schema.py"
    r = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"regenerator failed: {r.stderr}"

    # Check git diff on generated files.
    r2 = subprocess.run(
        ["git", "diff", "--exit-code", "docs/execute_command_schema.md",
         "schemas/execute_command.schema.json"],
        capture_output=True, text=True,
    )
    assert r2.returncode == 0, (
        f"Generated files have drifted from code. "
        f"Run `python scripts/generate_execute_command_schema.py` and commit:\n"
        f"{r2.stdout}"
    )
