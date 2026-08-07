"""Per-CommandAction MCP tool definitions and dispatch.

One MCP tool per ``CommandAction`` enum value. Each tool's ``input_schema``
is derived from the corresponding Pydantic args model via
``.model_json_schema()``, with ``justification`` and ``expected_effect``
prepended to every schema (they're required on every ``ExecuteCommand``).

The dispatch function builds an ``ExecuteCommand`` from a tool name and
arguments dict — the shape the real ``@server.call_tool()`` handler receives.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.types import Tool

from hackrf_agent.domain.args import ARGS_BY_ACTION
from hackrf_agent.domain.models import CommandAction, ExecuteCommand

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-action tool definitions
# ---------------------------------------------------------------------------

_TOOL_DESCRIPTIONS: dict[str, str] = {
    "get_device_info": "Read the attached HackRF's serial, firmware, and board revision. Always safe; no RF activity.",
    "sweep_spectrum": "RX-only sweep over a frequency band. Returns top-N peaks and noise floor. Safe for RX-allowed bands.",
    "capture_iq": "RX capture raw IQ samples to disk. Short captures (≤5s) are LOW risk; longer captures require approval.",
    "transmit_iq": "TX from an existing .iq file. Requires an active grant. HIGH risk in unclassified bands.",
    "read_iq_summary": "Re-summarize a previously captured .iq file. No hardware access; reads from disk only.",
    "decode_ook": "Attempt OOK bit decoding of an .iq file (placeholder). No hardware access.",
    "grant_list": "List currently active TX grants. Read-only administrative action.",
    "audit_query": "Query the audit log for recent events. Read-only administrative action.",
    "analyze_iq_modulation": "Moment-based modulation classifier over a captured .iq file. Returns ranked candidate families. LOW risk; reads from disk only.",
    "analyze_iq_symbols": "Estimate symbol rate from a captured .iq file via magnitude-squared autocorrelation. LOW risk; reads from disk only.",
    "analyze_iq_spectrogram": "Compact per-slice spectrogram summary (peak frequency + power per slice). LOW risk; reads from disk only.",
    "decode_manchester": "Manchester line-code decoder over an OOK envelope. Args include symbol_rate_hz and polarity (ieee|thomas).",
    "decode_pwm": "Pulse-width-modulation decoder over an OOK envelope. Args: short_us and long_us pulse widths.",
    "decode_ppm": "Pulse-position-modulation decoder over an OOK envelope. Args: pulse_us (symbol period is 2x).",
    "decode_nrz": "NRZ / NRZI line-code decoder. variant='nrz' or 'nrzi'; symbol_rate_hz required.",
    "decode_pocsag": "POCSAG paging decoder (baud 512/1200/2400). Args: iq_path, sample_rate_hz, baud. Returns per-message ric, function, numeric+alpha payloads. LOW risk; reads from disk only.",
    "decode_ads_b": "Mode S / ADS-B decoder for 1090 MHz captures. Requires sample_rate_hz >= 2 MHz. Returns per-frame df, icao24, raw hex, and CRC status. Read-only; RX-only band. TX on 1090 MHz remains BLOCKED regardless.",
    "decode_rtty": "RTTY / Baudot ITA2 decoder over 2FSK. Args: iq_path, sample_rate_hz, baud (default 45.45), invert. Returns decoded text with shift-state tracking. LOW risk; reads from disk only.",
    "decode_ax25": "AX.25 packet-radio decoder (HDLC over Bell 202 AFSK-1200 or direct FSK-9600). Args: iq_path, sample_rate_hz, baud (default 1200), invert (usually irrelevant — AX.25 is polarity-tolerant via NRZI). Returns per-frame source/destination/digipeaters, control, PID, info, and CRC-16-CCITT status. LOW risk.",
    "decode_aprs": "APRS decoder — AX.25 UI-frame payloads interpreted as APRS (position/status/message/etc.). Same args as decode_ax25. Adds an 'aprs' dict per frame with parsed lat/lon or status/message body. LOW risk.",
    "knowledge_list_topics": "Enumerate every topic dir under knowledge/ and its markdown files. Read-only; no RF activity.",
    "knowledge_read": "Return one markdown file from knowledge/<topic>/<name>. Read-only; path-traversal-safe.",
    "knowledge_search": "Case-insensitive substring search across every corpus markdown file. Read-only.",
    "knowledge_lookup_band": "Given freq_hz, return the bands.json record(s) covering that frequency. Read-only.",
    "knowledge_lookup_modulation": "Given a modulation name/alias, return the modulations.json record. Read-only.",
    "knowledge_verify_claim": "Grade a factual claim against the trap catalog (true/false/needs_qualification/unverified). Read-only.",
}

# Fields that every tool schema must include (in addition to action-specific args).
_SHARED_REQUIRED_FIELDS: dict[str, dict[str, Any]] = {
    "justification": {
        "type": "string",
        "description": "Why the caller is invoking this action.",
        "minLength": 1,
    },
    "expected_effect": {
        "type": "string",
        "description": "What the caller expects to observe from this action.",
        "minLength": 1,
    },
}


def build_tool(action: CommandAction) -> Tool:
    """Build an MCP ``Tool`` from a ``CommandAction``.

    The tool's ``input_schema`` is assembled from:
    1. The Pydantic model's ``model_json_schema()`` for the action's typed args.
    2. Two additional required fields: ``justification`` and ``expected_effect``.
    """
    args_model = ARGS_BY_ACTION.get(action.value)
    if args_model is None:
        raise ValueError(f"Unknown action: {action.value}")

    # Start with the Pydantic model's JSON Schema.
    raw_schema: dict[str, Any] = args_model.model_json_schema()

    # Build the final object schema.
    properties: dict[str, Any] = {}
    required: list[str] = []

    # Add action-specific properties (skip "properties" key if not present, e.g. empty model).
    for prop_name, prop_schema in raw_schema.get("properties", {}).items():
        properties[prop_name] = prop_schema

    # Add shared fields.
    properties.update(_SHARED_REQUIRED_FIELDS)
    required.extend(list(_SHARED_REQUIRED_FIELDS.keys()))

    # Add action-specific required fields.
    required.extend(raw_schema.get("required", []))

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
    }

    return Tool(
        name=f"hackrf_{action.value}",
        description=_TOOL_DESCRIPTIONS.get(action.value, f"Execute {action.value}"),
        input_schema=input_schema,
    )


# Pre-built tool list — cached at import time.
ALL_TOOLS: dict[str, Tool] = {
    action.value: build_tool(action) for action in CommandAction
}


def list_tools() -> list[Tool]:
    """Return the full MCP tool list (one per ``CommandAction``)."""
    return list(ALL_TOOLS.values())


# ---------------------------------------------------------------------------
# Dispatch — MCP tool call → ExecuteCommand
# ---------------------------------------------------------------------------


def dispatch(name: str, arguments: dict[str, Any]) -> ExecuteCommand:
    """Build an ``ExecuteCommand`` from a tool name and arguments.

    The tool name is expected to be ``hackrf_{action_value}`` (e.g.
    ``hackrf_sweep_spectrum``). The ``arguments`` dict is destructured
    into ``args``, ``justification``, and ``expected_effect``.
    """
    if not name.startswith("hackrf_"):
        raise ValueError(f"Unknown tool: {name!r}")

    action_value = name[len("hackrf_"):]

    try:
        action = CommandAction(action_value)
    except ValueError:
        raise ValueError(f"Unknown action {action_value!r} in tool {name!r}") from None

    # Split out shared fields from action-specific args (copy to avoid
    # mutating the caller's dict).
    args_copy = dict(arguments)
    justification = args_copy.pop("justification", "")
    expected_effect = args_copy.pop("expected_effect", "")

    # Validate action-specific args through the Pydantic model.
    args_model = ARGS_BY_ACTION.get(action_value)
    if args_model is not None:
        parsed = args_model(**args_copy)
        args = parsed.model_dump()
    else:
        args = args_copy

    return ExecuteCommand(
        action=action,
        args=args,
        justification=justification,
        expected_effect=expected_effect,
    )
