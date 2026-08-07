#!/usr/bin/env python3
"""Regenerate docs/execute_command_schema.md and
schemas/execute_command.schema.json from CommandAction + Pydantic models.

Wired into a pre-commit hook so drift between code and reference is
impossible: the hook regenerates and fails the commit if the diff is
non-empty.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hackrf_agent.ai.prompts import EXECUTE_COMMAND_TOOL_SCHEMA
from hackrf_agent.domain.models import CommandAction

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_JSON_PATH = REPO_ROOT / "schemas" / "execute_command.schema.json"
SCHEMA_MD_PATH = REPO_ROOT / "docs" / "execute_command_schema.md"


# Per-action human documentation. Each entry: (purpose, args_doc,
# example_envelope, default_tier, notes).
# When adding a new CommandAction, add its row here — a Part 8 test
# asserts every CommandAction has an entry.
PER_ACTION_DOCS: dict[CommandAction, dict[str, str]] = {
    CommandAction.GET_DEVICE_INFO: {
        "purpose": "Read the attached HackRF's serial, firmware, and board revision.",
        "args_doc": "No arguments.",
        "example": '{"action": "get_device_info", "args": {}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Always safe; no RF activity.",
    },
    CommandAction.SWEEP_SPECTRUM: {
        "purpose": "RX-only sweep over a band; returns top-N peaks and noise floor.",
        "args_doc": (
            "start_freq_hz (int), end_freq_hz (int), sample_rate_hz (int, default 2000000), "
            "lna_gain_db (int, default 16), vga_gain_db (int, default 20), "
            "rf_amp_db (int, default 0), dwell_s (float, default 1.0), "
            "fft_size (int, default 4096)."
        ),
        "example": '{"action": "sweep_spectrum", "args": '
                   '{"start_freq_hz": 433000000, "end_freq_hz": 434000000}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "RX only. Always safe within legal RX-allowed bands.",
    },
    CommandAction.CAPTURE_IQ: {
        "purpose": "RX capture into an .iq file under the session directory.",
        "args_doc": (
            "center_freq_hz (int, optional — explicit tuner center), "
            "target_freq_hz (int, optional — frequency of interest; tuner is "
            "offset by ~sample_rate/4 so the DC/LO spike lands in a different "
            "bin), sample_rate_hz (int, default 2000000), "
            "duration_s (float, required), lna_gain_db (int, default 16), "
            "vga_gain_db (int, default 20), rf_amp_db (int, default 0). "
            "Exactly one of center_freq_hz or target_freq_hz must be provided. "
            "The HackRF's local oscillator leaks a DC spike at the tuned "
            "center frequency, so tuning center=F to look at F puts a fake "
            "peak on top of the real signal. target_freq_hz avoids this by "
            "offsetting the tuner; use center_freq_hz only for raw tuner "
            "control."
        ),
        "example": '{"action": "capture_iq", "args": '
                   '{"target_freq_hz": 433925000, "sample_rate_hz": 8000000, '
                   '"duration_s": 2.0}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW under 5s; MEDIUM above",
        "notes": "Output file lives under session.iq_dir; path is synthesized "
                 "by the executor, not the LLM. Response includes both "
                 "center_hz (what the tuner was set to) and target_hz (the "
                 "requested target, null when center_freq_hz was used).",
    },
    CommandAction.TRANSMIT_IQ: {
        "purpose": "TX from an existing .iq file. Requires an active grant.",
        "args_doc": (
            "center_freq_hz (int), sample_rate_hz (int, default 2000000), "
            "iq_path (str, must be under session root), tx_vga_gain_db (int, required), "
            "rf_amp_db (int, default 0)."
        ),
        "example": '{"action": "transmit_iq", "args": '
                   '{"center_freq_hz": 433925000, "iq_path": "...", '
                   '"tx_vga_gain_db": 10}, "justification": "...", '
                   '"expected_effect": "..."}',
        "default_tier": "MEDIUM in-grant ISM; HIGH out-of-grant; BLOCKED in protected bands",
        "notes": "Never invoked without a matching PermissionService grant. "
                 "iq_path must be inside the session root.",
    },
    CommandAction.READ_IQ_SUMMARY: {
        "purpose": "Re-summarize a previously captured .iq file.",
        "args_doc": "iq_path (str), center_freq_hz (int), sample_rate_hz (int).",
        "example": '{"action": "read_iq_summary", "args": '
                   '{"iq_path": "...", "center_freq_hz": 433925000}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "No hardware access; runs FFT on disk contents.",
    },
    CommandAction.DECODE_OOK: {
        "purpose": "Attempt OOK bit decoding of an .iq file (placeholder).",
        "args_doc": "iq_path (str).",
        "example": '{"action": "decode_ook", "args": {"iq_path": "..."}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Placeholder — returns empty bits + a note until Part 9.",
    },
    CommandAction.GRANT_LIST: {
        "purpose": "List currently active TX grants.",
        "args_doc": "No arguments.",
        "example": '{"action": "grant_list", "args": {}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Read-only query against the permission service.",
    },
    CommandAction.AUDIT_QUERY: {
        "purpose": "Query the audit log; returns recent rows.",
        "args_doc": "session_id (str, optional), limit (int, default 50).",
        "example": '{"action": "audit_query", "args": {"limit": 10}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Read-only.",
    },
    CommandAction.ANALYZE_IQ_MODULATION: {
        "purpose": "Moment-based modulation classifier over a captured .iq file.",
        "args_doc": "iq_path (str), sample_rate_hz (int, default 2000000).",
        "example": '{"action": "analyze_iq_modulation", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 2000000}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Reads iq_path from the session dir; no libhackrf. Returns "
                 "a ranked list of candidate families with heuristic "
                 "confidence — treat as a starting point, not ML-verified.",
    },
    CommandAction.ANALYZE_IQ_SYMBOLS: {
        "purpose": "Estimate symbol rate via magnitude-squared autocorrelation.",
        "args_doc": "iq_path (str), sample_rate_hz (int, default 2000000), "
                    "min_rate_hz (float, default 100), max_rate_hz (float, "
                    "optional; default sample_rate_hz/8).",
        "example": '{"action": "analyze_iq_symbols", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 2000000, '
                   '"min_rate_hz": 500}, "justification": "...", '
                   '"expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Returns symbol_rate_hz + confidence + lag_samples.",
    },
    CommandAction.ANALYZE_IQ_SPECTROGRAM: {
        "purpose": "Compact per-slice spectrogram summary (peak freq + power).",
        "args_doc": "iq_path (str), sample_rate_hz (int), fft_size (int, "
                    "default 1024), overlap (float, default 0.5), "
                    "max_slices (int, default 512).",
        "example": '{"action": "analyze_iq_spectrogram", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 2000000, '
                   '"fft_size": 1024}, "justification": "...", '
                   '"expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Returns arrays of peak_freqs_hz + peak_dbfs — one entry "
                 "per slice, subsampled to max_slices when needed. Never "
                 "returns the full FFT matrix.",
    },
    CommandAction.DECODE_MANCHESTER: {
        "purpose": "Manchester line-code decoder over an OOK envelope.",
        "args_doc": "iq_path (str), sample_rate_hz (int), symbol_rate_hz "
                    "(float, required), polarity ('ieee'|'thomas', "
                    "default 'ieee').",
        "example": '{"action": "decode_manchester", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 2000000, '
                   '"symbol_rate_hz": 2048.0}, "justification": "...", '
                   '"expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Returns bits + invalid_pairs (symbol-timing errors). "
                 "IEEE 802.3 polarity: 01->1, 10->0. G.E. Thomas: swap.",
    },
    CommandAction.DECODE_PWM: {
        "purpose": "Pulse-width-modulation decoder over an OOK envelope.",
        "args_doc": "iq_path (str), sample_rate_hz (int), short_us (float, "
                    "required), long_us (float, required).",
        "example": '{"action": "decode_pwm", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 2000000, '
                   '"short_us": 400, "long_us": 800}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "0 = short pulse, 1 = long pulse. Returns bits + "
                 "pulse_widths_us + invalid_pulses.",
    },
    CommandAction.DECODE_PPM: {
        "purpose": "Pulse-position-modulation decoder over an OOK envelope.",
        "args_doc": "iq_path (str), sample_rate_hz (int), pulse_us (float, "
                    "required; symbol period is 2*pulse_us).",
        "example": '{"action": "decode_ppm", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 2000000, '
                   '"pulse_us": 400}, "justification": "...", '
                   '"expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Pulse in the first half of the symbol slot = 1; second "
                 "half = 0.",
    },
    CommandAction.DECODE_NRZ: {
        "purpose": "NRZ / NRZI line-code decoder.",
        "args_doc": "iq_path (str), sample_rate_hz (int), symbol_rate_hz "
                    "(float, required), variant ('nrz'|'nrzi', default "
                    "'nrz'), inverted (bool, default false).",
        "example": '{"action": "decode_nrz", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 2000000, '
                   '"symbol_rate_hz": 9600}, "justification": "...", '
                   '"expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "'nrz' = level encodes bit directly; 'nrzi' = transition "
                 "encodes a 1.",
    },
    CommandAction.DECODE_POCSAG: {
        "purpose": "POCSAG paging decoder (baud 512/1200/2400).",
        "args_doc": "iq_path (str), sample_rate_hz (int), baud (int in "
                    "{512, 1200, 2400}, default 1200).",
        "example": '{"action": "decode_pocsag", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 2000000, '
                   '"baud": 1200}, "justification": "...", '
                   '"expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Returns per-message ric, function, and both numeric-BCD "
                 "and 7-bit-ASCII payload strings. Also reports sync-word "
                 "offsets and per-codeword BCH validity.",
    },
    CommandAction.DECODE_ADS_B: {
        "purpose": "Mode S / ADS-B decoder for 1090 MHz captures.",
        "args_doc": "iq_path (str), sample_rate_hz (int, >= 2000000), "
                    "max_frames (int, default 64).",
        "example": '{"action": "decode_ads_b", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 2000000}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Read-only over already-captured IQ. TX on 1090 MHz "
                 "stays BLOCKED regardless. Returns per-frame df, "
                 "icao24_hex, raw_hex, crc_ok.",
    },
    CommandAction.KNOWLEDGE_LIST_TOPICS: {
        "purpose": "Enumerate every topic dir under knowledge/ and its markdown files.",
        "args_doc": "No arguments.",
        "example": '{"action": "knowledge_list_topics", "args": {}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Read-only; reads from disk under knowledge/. Never touches libhackrf.",
    },
    CommandAction.KNOWLEDGE_READ: {
        "purpose": "Return the contents of one markdown file under knowledge/<topic>/.",
        "args_doc": "topic (str, e.g. 'dsp'), name (str, e.g. 'README.md').",
        "example": '{"action": "knowledge_read", "args": '
                   '{"topic": "dsp", "name": "reference.md"}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Path-traversal-safe (topic/name matched against safe-name regexes). "
                 "1 MB per-file cap. Only .md files are readable via this verb; "
                 "records/*.json is exposed via knowledge_lookup_* verbs.",
    },
    CommandAction.KNOWLEDGE_SEARCH: {
        "purpose": "Case-insensitive substring search across every corpus markdown file.",
        "args_doc": "query (str), max_results (int, default 20, 1-200).",
        "example": '{"action": "knowledge_search", "args": '
                   '{"query": "Manchester", "max_results": 10}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Prefer a knowledge_lookup_* verb when a typed lookup fits the question.",
    },
    CommandAction.KNOWLEDGE_LOOKUP_BAND: {
        "purpose": "Return the bands.json record(s) covering freq_hz.",
        "args_doc": "freq_hz (int, 1 Hz-6 GHz).",
        "example": '{"action": "knowledge_lookup_band", "args": '
                   '{"freq_hz": 433920000}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Multiple matches are possible where allocations overlap "
                 "(e.g. EU ISM 433 sits inside US amateur 70 cm).",
    },
    CommandAction.KNOWLEDGE_LOOKUP_MODULATION: {
        "purpose": "Return the modulations.json record for a named modulation family.",
        "args_doc": "name (str, e.g. 'OOK', 'GFSK', '2FSK', 'LoRa').",
        "example": '{"action": "knowledge_lookup_modulation", "args": '
                   '{"name": "GFSK"}, "justification": "...", '
                   '"expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Matches on name, id, or aliases (case-insensitive). "
                 "Returns null when no record matches.",
    },
    CommandAction.KNOWLEDGE_VERIFY_CLAIM: {
        "purpose": "Grade a factual claim against the trap catalog.",
        "args_doc": "text (str, 1-1000 chars).",
        "example": '{"action": "knowledge_verify_claim", "args": '
                   '{"text": "The HackRF can transmit on ADS-B."}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Returns verdict in {true, false, needs_qualification, unverified} "
                 "with citations. 'unverified' means no trap fired — caveat "
                 "accordingly.",
    },
}


def _render_markdown() -> str:
    """Build the docs/execute_command_schema.md content."""
    lines = [
        "# `execute_command` — action reference",
        "",
        "> AUTO-GENERATED. Do not edit. Regenerate with "
        "`python scripts/generate_execute_command_schema.py`.",
        "",
        "The one tool exposed to the LLM. Every RF action goes through it. "
        "The envelope shape is:",
        "",
        "```json",
        '{"action": "<one of the actions below>", "args": {...}, '
        '"justification": "...", "expected_effect": "..."}',
        "```",
        "",
    ]
    for action in CommandAction:
        entry = PER_ACTION_DOCS.get(action)
        if entry is None:
            raise RuntimeError(
                f"CommandAction.{action.name} has no docs entry in "
                f"PER_ACTION_DOCS. Add one before regenerating."
            )
        lines.extend([
            f"## `{action.value}`",
            "",
            f"**Purpose.** {entry['purpose']}",
            "",
            f"**Args.** {entry['args_doc']}",
            "",
            f"**Default risk tier.** {entry['default_tier']}",
            "",
            "**Example envelope.**",
            "",
            "```json",
            entry["example"],
            "```",
            "",
            f"**Notes.** {entry['notes']}",
            "",
        ])
    return "\n".join(lines) + "\n"


def main() -> None:
    # JSON schema.
    SCHEMA_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_JSON_PATH.write_text(
        json.dumps(EXECUTE_COMMAND_TOOL_SCHEMA, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # Markdown reference.
    SCHEMA_MD_PATH.write_text(_render_markdown(), encoding="utf-8")
    print(f"wrote {SCHEMA_JSON_PATH}")
    print(f"wrote {SCHEMA_MD_PATH}")


if __name__ == "__main__":
    main()
