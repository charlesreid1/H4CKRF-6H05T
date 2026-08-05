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

**Args.** center_freq_hz (int, optional — explicit tuner center), target_freq_hz (int, optional — frequency of interest; tuner is offset by ~sample_rate/4 so the DC/LO spike lands in a different bin), sample_rate_hz (int, default 2000000), duration_s (float, required), lna_gain_db (int, default 16), vga_gain_db (int, default 20), rf_amp_db (int, default 0). Exactly one of center_freq_hz or target_freq_hz must be provided. The HackRF's local oscillator leaks a DC spike at the tuned center frequency, so tuning center=F to look at F puts a fake peak on top of the real signal. target_freq_hz avoids this by offsetting the tuner; use center_freq_hz only for raw tuner control.

**Default risk tier.** LOW under 5s; MEDIUM above

**Example envelope.**

```json
{"action": "capture_iq", "args": {"target_freq_hz": 433925000, "sample_rate_hz": 8000000, "duration_s": 2.0}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Output file lives under session.iq_dir; path is synthesized by the executor, not the LLM. Response includes both center_hz (what the tuner was set to) and target_hz (the requested target, null when center_freq_hz was used).

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

## `analyze_pulses`

**Purpose.** Run rtl_433 -A on a captured IQ file to estimate pulse timing, guess the modulation family (OOK/PPM/PWM/Manchester), and match against known device protocols.

**Args.** iq_path (str), sample_rate_hz (int).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "analyze_pulses", "args": {"iq_path": "...", "sample_rate_hz": 2000000}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Requires rtl_433 installed on the host (brew install rtl_433). Returns pulse stats, modulation guess, and any protocol matches. The old action name "decode_ook" is accepted as an alias.

## `demodulate_bits`

**Purpose.** Run urh_cli on a captured IQ file with explicit demod parameters to extract a raw bitstream. No protocol matching — caller recognises framing, CRC, sync words.

**Args.** iq_path (str), sample_rate_hz (int), modulation (str: ASK/FSK/GFSK/PSK), samples_per_symbol (int), threshold (float, optional), invert (bool, optional), bit_order (str, optional: lsb/msb).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "demodulate_bits", "args": {"iq_path": "...", "sample_rate_hz": 2000000, "modulation": "ASK", "samples_per_symbol": 1000}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Requires URH installed on the host (pipx install urh). Recommended workflow: run analyze_pulses first, then feed its estimated_symbol_rate_hz and modulation guess into demodulate_bits.

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

