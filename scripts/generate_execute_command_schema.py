#!/usr/bin/env python3
"""Regenerate docs/execute_command_schema.md,
schemas/execute_command.schema.json, and the MCP tools table in
docs/mcp.md from CommandAction + Pydantic models.

Wired into a pre-commit hook so drift between code and reference is
impossible: the hook regenerates and fails the commit if the diff is
non-empty.

Usage:
    python scripts/generate_execute_command_schema.py            # regenerate
    python scripts/generate_execute_command_schema.py --check    # fail if diff
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from hackrf_agent.ai.prompts import EXECUTE_COMMAND_TOOL_SCHEMA
from hackrf_agent.domain.models import CommandAction

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_JSON_PATH = REPO_ROOT / "schemas" / "execute_command.schema.json"
SCHEMA_MD_PATH = REPO_ROOT / "docs" / "execute_command_schema.md"
MCP_MD_PATH = REPO_ROOT / "docs" / "mcp.md"
MCP_TABLE_BEGIN = "<!-- BEGIN AUTO-GENERATED MCP TOOLS TABLE -->"
MCP_TABLE_END = "<!-- END AUTO-GENERATED MCP TOOLS TABLE -->"


# Per-action human documentation. Each entry: (purpose, args_doc,
# example_envelope, default_tier, notes).
# When adding a new CommandAction, add its row here — a test in
# tests/unit/ asserts every CommandAction has an entry.
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
        "notes": "RX only. Always safe within legal RX-allowed bands. "
                 "The driver tunes to (start+stop)/2; when the requested "
                 "span exceeds sample_rate_hz, the result carries "
                 "truncated=true — fall back to sweep_spectrum_bulk with "
                 "explicit sub-ranges ≤ sample_rate_hz each.",
    },
    CommandAction.SWEEP_SPECTRUM_BULK: {
        "purpose": "Sweep multiple bands in one call (2-8 ranges).",
        "args_doc": (
            "ranges (list of {start_freq_hz, end_freq_hz}, length 2-8), "
            "sample_rate_hz (int, default 2000000), lna_gain_db (int, "
            "default 16), vga_gain_db (int, default 20), rf_amp_db (int, "
            "default 0), dwell_s (float, default 1.0), fft_size (int, "
            "default 4096). Shared across all ranges."
        ),
        "example": '{"action": "sweep_spectrum_bulk", "args": '
                   '{"ranges": [{"start_freq_hz": 315000000, "end_freq_hz": 316000000}, '
                   '{"start_freq_hz": 433000000, "end_freq_hz": 435000000}]}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW at dwell_s <= 2s; MEDIUM above",
        "notes": "Returns {num_ranges, sweeps} where each sweep entry has "
                 "the same shape as sweep_spectrum's result. Per-range "
                 "risk classification applies at the driver level.",
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
    CommandAction.ANALYZE_IQ_CARRIER_FREQUENCY: {
        "purpose": "Refine the actual carrier-frequency offset in a capture.",
        "args_doc": "iq_path (str), sample_rate_hz (int), "
                    "fft_size (int, default 8192, 256-65536).",
        "example": '{"action": "analyze_iq_carrier_frequency", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 2000000}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Returns carrier_offset_hz (from baseband centre), "
                 "peak_dbfs, bin_resolution_hz, confidence (dB peak-to-"
                 "noise). Sub-bin refinement via parabolic interpolation.",
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
    CommandAction.DECODE_RTTY: {
        "purpose": "RTTY / Baudot ITA2 decoder over a 2FSK envelope.",
        "args_doc": "iq_path (str), sample_rate_hz (int), baud (float, "
                    "default 45.45), invert (bool, default false).",
        "example": '{"action": "decode_rtty", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 2000000, '
                   '"baud": 45.45}, "justification": "...", '
                   '"expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Returns decoded text (with LTRS/FIGS shift-state "
                 "tracking) plus framing_errors count. Try invert=true "
                 "if the decoded text is nonsense but num_characters is "
                 "nonzero — some transmitters swap MARK/SPACE polarity.",
    },
    CommandAction.DECODE_AX25: {
        "purpose": "AX.25 packet-radio decoder (HDLC over Bell 202 AFSK-1200 or direct FSK-9600).",
        "args_doc": "iq_path (str), sample_rate_hz (int), baud (float, "
                    "default 1200), invert (bool, default false).",
        "example": '{"action": "decode_ax25", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 48000, '
                   '"baud": 1200}, "justification": "...", '
                   '"expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Returns per-frame destination/source/digipeaters, control, "
                 "PID, info bytes, and CRC-16-CCITT status. NRZI + "
                 "bit-unstuffing handled internally.",
    },
    CommandAction.DECODE_APRS: {
        "purpose": "APRS decoder - AX.25 UI frames with APRS payload interpretation.",
        "args_doc": "iq_path (str), sample_rate_hz (int), baud (float, "
                    "default 1200), invert (bool, default false).",
        "example": '{"action": "decode_aprs", "args": '
                   '{"iq_path": "...", "sample_rate_hz": 48000}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Recognized DTIs: !/= (position no-ts), //@  (position ts), "
                 "> (status), : (message), ; (object), T (telemetry). "
                 "Position reports return lat/lon in decimal degrees.",
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
    CommandAction.KNOWLEDGE_LOOKUP_PROTOCOL: {
        "purpose": "Return the protocols.json record for a named protocol.",
        "args_doc": "name (str, e.g. 'POCSAG', 'ADS-B', 'AX.25', 'LoRaWAN').",
        "example": '{"action": "knowledge_lookup_protocol", "args": '
                   '{"name": "POCSAG"}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Matches on name, id, or aliases (case-insensitive). "
                 "Returns null when no record matches.",
    },
    CommandAction.KNOWLEDGE_LOOKUP_KEYFOB: {
        "purpose": "Return keyfob-system records matching vendor and/or model.",
        "args_doc": "vendor (str, optional), model (str, optional). "
                    "At least one must be provided.",
        "example": '{"action": "knowledge_lookup_keyfob", "args": '
                   '{"vendor": "Chamberlain"}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Substring matches, case-insensitive. Returns every matching "
                 "record; the caller picks the closest generation.",
    },
    CommandAction.KNOWLEDGE_LOOKUP_DECODER: {
        "purpose": "Return the decoders.json record for a named decoder family.",
        "args_doc": "name (str, e.g. 'Manchester', 'NRZ', 'PWM', 'PPM').",
        "example": '{"action": "knowledge_lookup_decoder", "args": '
                   '{"name": "Manchester"}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Each record links to the paired analyze_iq_* / decode_* verb "
                 "via tools_downstream.",
    },
    CommandAction.KNOWLEDGE_BIBLIOGRAPHY: {
        "purpose": "Return one bibliography citation by id, or the full list.",
        "args_doc": "cite_id (str, optional). Omit to list every citation.",
        "example": '{"action": "knowledge_bibliography", "args": '
                   '{"cite_id": "fcc-part-15"}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Returns an empty list when cite_id has no match.",
    },
    CommandAction.KNOWLEDGE_RANDOM: {
        "purpose": "Return one random markdown file from the corpus.",
        "args_doc": "seed (int, optional) for deterministic selection.",
        "example": '{"action": "knowledge_random", "args": {}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Uses SystemRandom when seed is unset; the same seed always "
                 "picks the same file.",
    },
    CommandAction.KNOWLEDGE_EXPLAIN_SIGNAL: {
        "purpose": "Rank candidate signals from known_signals.json given hints.",
        "args_doc": "freq_hz (int, optional), bw_hz (int, optional), "
                    "modulation_guess (str, optional), max_results (int, "
                    "default 5). At least one hint required.",
        "example": '{"action": "knowledge_explain_signal", "args": '
                   '{"freq_hz": 433920000, "modulation_guess": "OOK"}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Score is the sum of matched hints (each contributes 1.0). "
                 "Ties broken by record id.",
    },
    CommandAction.KNOWLEDGE_CROSS_REFERENCE: {
        "purpose": "Traverse see_also across every records/*.json file.",
        "args_doc": "record_id (str, e.g. 'protocol-pocsag-1200').",
        "example": '{"action": "knowledge_cross_reference", "args": '
                   '{"record_id": "protocol-pocsag-1200"}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW",
        "notes": "Returns {record, related, unresolved}. unresolved holds ids "
                 "that no records file exports.",
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
    CommandAction.PLAY_SEQUENCE: {
        "purpose": "Chain 2-8 sub-actions through the funnel in order.",
        "args_doc": "steps (list of {action, args}, 2-8 items), "
                    "stop_on_error (bool, default true).",
        "example": '{"action": "play_sequence", "args": {"steps": '
                   '[{"action": "analyze_iq_modulation", "args": {"iq_path": "..."}}, '
                   '{"action": "analyze_iq_symbols", "args": {"iq_path": "..."}}]}, '
                   '"justification": "...", "expected_effect": "..."}',
        "default_tier": "LOW (per-step risk applies)",
        "notes": "Each sub-action re-enters CommandExecutor.execute() with "
                 "its own risk assessment, permission check, approval flow, "
                 "and audit trail. No batching bypass. play_sequence cannot "
                 "nest inside itself. stop_on_error=false runs every step "
                 "even after a failure.",
    },
}


# ---------------------------------------------------------------------------
# MCP-table metadata: group each action into Know / Analyze / Act / Compose,
# plus the RF-activity column for the mcp.md tools table.
# ---------------------------------------------------------------------------
_KNOW_ACTIONS: set[CommandAction] = {
    CommandAction.KNOWLEDGE_LIST_TOPICS,
    CommandAction.KNOWLEDGE_READ,
    CommandAction.KNOWLEDGE_SEARCH,
    CommandAction.KNOWLEDGE_LOOKUP_BAND,
    CommandAction.KNOWLEDGE_LOOKUP_MODULATION,
    CommandAction.KNOWLEDGE_LOOKUP_PROTOCOL,
    CommandAction.KNOWLEDGE_LOOKUP_KEYFOB,
    CommandAction.KNOWLEDGE_LOOKUP_DECODER,
    CommandAction.KNOWLEDGE_BIBLIOGRAPHY,
    CommandAction.KNOWLEDGE_RANDOM,
    CommandAction.KNOWLEDGE_EXPLAIN_SIGNAL,
    CommandAction.KNOWLEDGE_CROSS_REFERENCE,
    CommandAction.KNOWLEDGE_VERIFY_CLAIM,
}
_ANALYZE_ACTIONS: set[CommandAction] = {
    CommandAction.READ_IQ_SUMMARY,
    CommandAction.ANALYZE_IQ_MODULATION,
    CommandAction.ANALYZE_IQ_SYMBOLS,
    CommandAction.ANALYZE_IQ_SPECTROGRAM,
    CommandAction.ANALYZE_IQ_CARRIER_FREQUENCY,
    CommandAction.DECODE_MANCHESTER,
    CommandAction.DECODE_PWM,
    CommandAction.DECODE_PPM,
    CommandAction.DECODE_NRZ,
    CommandAction.DECODE_POCSAG,
    CommandAction.DECODE_ADS_B,
    CommandAction.DECODE_RTTY,
    CommandAction.DECODE_AX25,
    CommandAction.DECODE_APRS,
}
_COMPOSE_ACTIONS: set[CommandAction] = {
    CommandAction.PLAY_SEQUENCE,
}
# Everything else = Act tier.

_RF_ACTIVITY: dict[CommandAction, str] = {
    CommandAction.GET_DEVICE_INFO: "none",
    CommandAction.SWEEP_SPECTRUM: "RX only",
    CommandAction.SWEEP_SPECTRUM_BULK: "RX only",
    CommandAction.CAPTURE_IQ: "RX only",
    CommandAction.TRANSMIT_IQ: "TX",
    CommandAction.PLAY_SEQUENCE: "per-step",
    CommandAction.GRANT_LIST: "none",
    CommandAction.AUDIT_QUERY: "none",
}


def _action_group(action: CommandAction) -> str:
    if action in _KNOW_ACTIONS:
        return "Know"
    if action in _ANALYZE_ACTIONS:
        return "Analyze"
    if action in _COMPOSE_ACTIONS:
        return "Compose"
    return "Act"


def _rf_activity(action: CommandAction) -> str:
    return _RF_ACTIVITY.get(action, "none")


def _render_mcp_tools_table() -> str:
    """Build the MCP tools table for docs/mcp.md, grouped by tier."""
    groups: dict[str, list[CommandAction]] = {
        "Know": [],
        "Analyze": [],
        "Act": [],
        "Compose": [],
    }
    for action in CommandAction:
        groups[_action_group(action)].append(action)

    lines: list[str] = [MCP_TABLE_BEGIN, ""]
    for group in ("Know", "Analyze", "Act", "Compose"):
        actions = groups[group]
        if not actions:
            continue
        lines.append(f"### {group} tier")
        lines.append("")
        lines.append("| MCP tool name | Underlying action | Risk (typical) | RF activity |")
        lines.append("|---|---|---|---|")
        for action in actions:
            entry = PER_ACTION_DOCS.get(action)
            tier = entry["default_tier"] if entry else "LOW"
            lines.append(
                f"| `hackrf_{action.value}` | `{action.name}` | {tier} | "
                f"{_rf_activity(action)} |"
            )
        lines.append("")
    lines.append(MCP_TABLE_END)
    return "\n".join(lines)


def _splice_mcp_table(current: str, new_table: str) -> str:
    """Replace the content between MCP_TABLE_BEGIN / MCP_TABLE_END markers."""
    begin_idx = current.find(MCP_TABLE_BEGIN)
    end_idx = current.find(MCP_TABLE_END)
    if begin_idx == -1 or end_idx == -1:
        raise RuntimeError(
            f"Markers {MCP_TABLE_BEGIN!r} / {MCP_TABLE_END!r} not found in "
            f"{MCP_MD_PATH}; add them where the MCP tools table should live."
        )
    end_idx += len(MCP_TABLE_END)
    return current[:begin_idx] + new_table + current[end_idx:]


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


def _generate() -> dict[Path, str]:
    """Return the target-path → intended-content map for every artefact."""
    outputs: dict[Path, str] = {}
    outputs[SCHEMA_JSON_PATH] = (
        json.dumps(EXECUTE_COMMAND_TOOL_SCHEMA, indent=2, sort_keys=True) + "\n"
    )
    outputs[SCHEMA_MD_PATH] = _render_markdown()

    mcp_current = MCP_MD_PATH.read_text(encoding="utf-8")
    outputs[MCP_MD_PATH] = _splice_mcp_table(mcp_current, _render_mcp_tools_table())
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any generated file differs from its "
             "current on-disk contents. Does not write anything.",
    )
    args = parser.parse_args()

    SCHEMA_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    outputs = _generate()

    if args.check:
        drift: list[Path] = []
        for path, want in outputs.items():
            have = path.read_text(encoding="utf-8") if path.exists() else ""
            if have != want:
                drift.append(path)
        if drift:
            for path in drift:
                print(f"drift: {path.relative_to(REPO_ROOT)}", file=sys.stderr)
            print(
                "\nRe-run `python scripts/generate_execute_command_schema.py` "
                "and commit the result.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("no drift")
        return

    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
