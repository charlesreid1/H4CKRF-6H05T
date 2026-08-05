# `execute_command` — action reference

> AUTO-GENERATED. Do not edit. Regenerate with `python scripts/generate_execute_command_schema.py`.

The one tool exposed to the LLM. Every RF action goes through it. The envelope shape is:

```json
{"action": "<one of the actions below>", "args": {...}, "justification": "...", "expected_effect": "..."}
```

## `get_device_info`

**Purpose.** Read the attached HackRF's serial, firmware, and board revision.

**Args.** No arguments.

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "get_device_info", "args": {}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Always safe; no RF activity.

## `sweep_spectrum`

**Purpose.** RX-only sweep over a band; returns top-N peaks and noise floor.

**Args.** start_freq_hz (int), end_freq_hz (int), sample_rate_hz (int, default 2000000), lna_gain_db (int, default 16), vga_gain_db (int, default 20), rf_amp_db (int, default 0), dwell_s (float, default 1.0), fft_size (int, default 4096).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "sweep_spectrum", "args": {"start_freq_hz": 433000000, "end_freq_hz": 434000000}, "justification": "...", "expected_effect": "..."}
```

**Notes.** RX only. Always safe within legal RX-allowed bands.

## `capture_iq`

**Purpose.** RX capture into an .iq file under the session directory.

**Args.** center_freq_hz (int, optional — explicit tuner center), target_freq_hz (int, optional — frequency of interest; tuner is offset by ~sample_rate/4 so the DC/LO spike lands in a different bin), sample_rate_hz (int, default 2000000), duration_s (float, required), lna_gain_db (int, default 16), vga_gain_db (int, default 20), rf_amp_db (int, default 0).

Exactly one of ``center_freq_hz`` or ``target_freq_hz`` must be provided.

**Why two fields?** The HackRF (like every direct-conversion SDR) has a DC spike at whatever frequency it is tuned to — its local oscillator leaks into the receive path and shows up as a large fake peak sitting exactly at the tuned center frequency. If you tune ``center = 433.92 MHz`` to look at a 433.92 MHz signal, the DC spike lands *on top of* the thing you're trying to see. The spike also moves with retuning: it's an artifact of the radio, not of the environment.

``target_freq_hz`` solves this. Instead of tuning the radio to your frequency of interest, the agent tunes it to ``target + sample_rate/4`` — the DC spike lands a quarter of the RX bandwidth away, safely in a different bin, while your target frequency stays inside the passband. The response tells you both the ``target_hz`` you asked for and the ``center_hz`` the tuner actually used.

Use ``center_freq_hz`` when you want raw tuner control (e.g. wideband surveying where the exact center doesn't matter, or when you're intentionally capturing the DC spike itself).

**Default risk tier.** LOW under 5s; MEDIUM above

**Example envelopes.**

```json
{"action": "capture_iq", "args": {"center_freq_hz": 433925000, "duration_s": 5.0}, "justification": "...", "expected_effect": "..."}
```

```json
{"action": "capture_iq", "args": {"target_freq_hz": 433925000, "sample_rate_hz": 8000000, "duration_s": 2.0}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Output file lives under session.iq_dir; path is synthesized by the executor, not the LLM. The response includes both ``center_hz`` (the frequency the tuner was actually set to) and ``target_hz`` (the requested target, null when ``center_freq_hz`` was used).

## `transmit_iq`

**Purpose.** TX from an existing .iq file. Requires an active grant.

**Args.** center_freq_hz (int), sample_rate_hz (int, default 2000000), iq_path (str, must be under session root), tx_vga_gain_db (int, required), rf_amp_db (int, default 0).

**Default risk tier.** MEDIUM in-grant ISM; HIGH out-of-grant; BLOCKED in protected bands

**Example envelope.**

```json
{"action": "transmit_iq", "args": {"center_freq_hz": 433925000, "iq_path": "...", "tx_vga_gain_db": 10}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Never invoked without a matching PermissionService grant. iq_path must be inside the session root.

## `read_iq_summary`

**Purpose.** Re-summarize a previously captured .iq file.

**Args.** iq_path (str), center_freq_hz (int), sample_rate_hz (int).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "read_iq_summary", "args": {"iq_path": "...", "center_freq_hz": 433925000}, "justification": "...", "expected_effect": "..."}
```

**Notes.** No hardware access; runs FFT on disk contents.

## `decode_ook`

**Purpose.** Attempt OOK bit decoding of an .iq file (placeholder).

**Args.** iq_path (str).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "decode_ook", "args": {"iq_path": "..."}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Placeholder — returns empty bits + a note until Part 9.

## `grant_list`

**Purpose.** List currently active TX grants.

**Args.** No arguments.

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "grant_list", "args": {}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Read-only query against the permission service.

## `audit_query`

**Purpose.** Query the audit log; returns recent rows.

**Args.** session_id (str, optional), limit (int, default 50).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "audit_query", "args": {"limit": 10}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Read-only.

