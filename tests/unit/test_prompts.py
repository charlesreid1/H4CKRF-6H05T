"""Unit tests for prompts.py — system prompt content, tool schema shape, stability."""

import importlib
import json
import re

from hackrf_agent.ai import prompts
from hackrf_agent.ai.prompts import (
    EXECUTE_COMMAND_TOOL_SCHEMA,
    MAX_TOOL_CALLS_PER_RESPONSE,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_VERSION,
    TOOL_NAME,
)
from hackrf_agent.domain.models import CommandAction

# ---------------------------------------------------------------------------
# System prompt tests
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    """Tests for the SYSTEM_PROMPT content and shape."""

    def test_contains_required_sections(self) -> None:
        """SYSTEM_PROMPT contains all six required sections."""
        lower = SYSTEM_PROMPT.lower()
        # Band chart / ISM references.
        assert "ism 315" in lower
        assert "ism 433" in lower
        # BLOCKED bands.
        assert "blocked" in lower
        # Tool name.
        assert "execute_command" in lower
        # Operating discipline.
        assert "sweep-before-capture" in lower
        # One tool call per response.
        assert "one tool call per response" in lower

    def test_contains_risk_tiers(self) -> None:
        """SYSTEM_PROMPT references all four risk tiers."""
        lower = SYSTEM_PROMPT.lower()
        assert "low" in lower
        assert "medium" in lower
        assert "high" in lower
        # "blocked" already checked above but verify in risk context.
        assert "blocked" in lower

    def test_no_datetime_interpolation(self) -> None:
        """SYSTEM_PROMPT does not contain a runtime datetime."""
        # The version string uses YYYY-MM-DD-vN without a 'T' separator.
        # A real datetime would have e.g. 2026-08-03T14:30:00.
        assert not re.search(r"\d{4}-\d{2}-\d{2}T", SYSTEM_PROMPT)

    def test_no_per_run_markers(self) -> None:
        """SYSTEM_PROMPT does not contain session IDs or UUIDs."""
        # No UUID pattern.
        assert not re.search(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            SYSTEM_PROMPT,
        )

    def test_contains_band_table_entries(self) -> None:
        """SYSTEM_PROMPT references key frequency bands."""
        assert "315 MHz" in SYSTEM_PROMPT
        assert "433.05" in SYSTEM_PROMPT
        assert "902–928" in SYSTEM_PROMPT or "902-928" in SYSTEM_PROMPT
        assert "2.4 GHz" in SYSTEM_PROMPT

    def test_contains_blocked_bands(self) -> None:
        """SYSTEM_PROMPT references blocked bands."""
        assert "1090 MHz" in SYSTEM_PROMPT
        assert "GPS L1" in SYSTEM_PROMPT
        assert "118–137" in SYSTEM_PROMPT or "118-137" in SYSTEM_PROMPT
        assert "156.7625" in SYSTEM_PROMPT

    def test_version_constant(self) -> None:
        """SYSTEM_PROMPT_VERSION matches YYYY-MM-DD-vN pattern."""
        assert re.match(r"^\d{4}-\d{2}-\d{2}-v\d+$", SYSTEM_PROMPT_VERSION)


# ---------------------------------------------------------------------------
# Tool schema tests
# ---------------------------------------------------------------------------


class TestToolSchema:
    """Tests for EXECUTE_COMMAND_TOOL_SCHEMA."""

    def test_name_is_execute_command(self) -> None:
        """The tool schema's name is 'execute_command'."""
        assert EXECUTE_COMMAND_TOOL_SCHEMA["function"]["name"] == "execute_command"

    def test_required_fields(self) -> None:
        """The parameters schema requires 'action', 'justification', 'expected_effect'."""
        required = EXECUTE_COMMAND_TOOL_SCHEMA["function"]["parameters"]["required"]
        assert "action" in required
        assert "justification" in required
        assert "expected_effect" in required

    def _get_action_enum(self) -> list[str]:
        """Resolve the action field's enum, which Pydantic v2 places under $defs."""
        schema = EXECUTE_COMMAND_TOOL_SCHEMA["function"]["parameters"]
        props = schema["properties"]
        # The action field may be a $ref to a definition, or inline.
        action_schema = props["action"]
        if "$ref" in action_schema:
            ref_path = action_schema["$ref"]  # e.g. "#/$defs/CommandAction"
            ref_key = ref_path.split("/")[-1]
            action_schema = schema["$defs"][ref_key]
        return action_schema["enum"]

    def test_action_enum_contains_all_command_actions(self) -> None:
        """The 'action' field's enum has all CommandAction string values."""
        action_enum = self._get_action_enum()

        expected = {a.value for a in CommandAction}
        actual = set(action_enum)

        # All expected values are present.
        assert expected == actual, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_action_enum_uses_string_values_not_names(self) -> None:
        """Enum values are the string values (e.g. 'get_device_info'), not enum names."""
        action_enum = self._get_action_enum()

        # Verify string values are used, not uppercase enum member names.
        assert "get_device_info" in action_enum
        assert "GET_DEVICE_INFO" not in action_enum
        assert "sweep_spectrum" in action_enum
        assert "SWEEP_SPECTRUM" not in action_enum

    def test_json_dumps_deterministic(self) -> None:
        """json.dumps(EXECUTE_COMMAND_TOOL_SCHEMA, sort_keys=True) is deterministic."""
        dump1 = json.dumps(EXECUTE_COMMAND_TOOL_SCHEMA, sort_keys=True)
        dump2 = json.dumps(EXECUTE_COMMAND_TOOL_SCHEMA, sort_keys=True)
        assert dump1 == dump2

    def test_schema_stable_across_reimport(self) -> None:
        """Reimporting the module yields an equal schema dict."""
        # Force a fresh import of the module.
        importlib.reload(prompts)
        schema2 = prompts.EXECUTE_COMMAND_TOOL_SCHEMA
        assert schema2 == EXECUTE_COMMAND_TOOL_SCHEMA

    def test_has_description(self) -> None:
        """The tool schema has a non-empty description."""
        desc = EXECUTE_COMMAND_TOOL_SCHEMA["function"].get("description", "")
        assert len(desc) > 50  # Should be a substantial description.

    def test_parameters_has_type_object(self) -> None:
        """The parameters schema's top-level type is 'object'."""
        assert EXECUTE_COMMAND_TOOL_SCHEMA["function"]["parameters"]["type"] == "object"

    def test_no_title_fields_in_schema(self) -> None:
        """Pydantic title fields are stripped from the schema."""

        def _find_titles(node: object) -> list[str]:
            found: list[str] = []
            if isinstance(node, dict):
                if "title" in node:
                    found.append(str(node["title"]))
                for v in node.values():
                    found.extend(_find_titles(v))
            elif isinstance(node, list):
                for v in node:
                    found.extend(_find_titles(v))
            return found

        titles = _find_titles(EXECUTE_COMMAND_TOOL_SCHEMA)
        # The only "title" we tolerate is if the top-level schema has one
        # that Pydantic v2 adds; but we strip everything.
        assert len(titles) == 0, f"Found unstripped titles: {titles}"


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module-level constants."""

    def test_max_tool_calls_per_response(self) -> None:
        """MAX_TOOL_CALLS_PER_RESPONSE == 1."""
        assert MAX_TOOL_CALLS_PER_RESPONSE == 1

    def test_tool_name_is_execute_command(self) -> None:
        """TOOL_NAME == 'execute_command'."""
        assert TOOL_NAME == "execute_command"

    def test_system_prompt_not_empty(self) -> None:
        """SYSTEM_PROMPT is a non-empty string."""
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 1000
