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

## `analyze_iq_modulation`

**Purpose.** Moment-based modulation classifier over a captured .iq file.

**Args.** iq_path (str), sample_rate_hz (int, default 2000000).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "analyze_iq_modulation", "args": {"iq_path": "...", "sample_rate_hz": 2000000}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Reads iq_path from the session dir; no libhackrf. Returns a ranked list of candidate families with heuristic confidence — treat as a starting point, not ML-verified.

## `analyze_iq_symbols`

**Purpose.** Estimate symbol rate via magnitude-squared autocorrelation.

**Args.** iq_path (str), sample_rate_hz (int, default 2000000), min_rate_hz (float, default 100), max_rate_hz (float, optional; default sample_rate_hz/8).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "analyze_iq_symbols", "args": {"iq_path": "...", "sample_rate_hz": 2000000, "min_rate_hz": 500}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Returns symbol_rate_hz + confidence + lag_samples.

## `analyze_iq_spectrogram`

**Purpose.** Compact per-slice spectrogram summary (peak freq + power).

**Args.** iq_path (str), sample_rate_hz (int), fft_size (int, default 1024), overlap (float, default 0.5), max_slices (int, default 512).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "analyze_iq_spectrogram", "args": {"iq_path": "...", "sample_rate_hz": 2000000, "fft_size": 1024}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Returns arrays of peak_freqs_hz + peak_dbfs — one entry per slice, subsampled to max_slices when needed. Never returns the full FFT matrix.

## `analyze_iq_carrier_frequency`

**Purpose.** Refine the actual carrier-frequency offset in a capture.

**Args.** iq_path (str), sample_rate_hz (int), fft_size (int, default 8192, 256-65536).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "analyze_iq_carrier_frequency", "args": {"iq_path": "...", "sample_rate_hz": 2000000}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Returns carrier_offset_hz (from baseband centre), peak_dbfs, bin_resolution_hz, confidence (dB peak-to-noise). Sub-bin refinement via parabolic interpolation.

## `decode_manchester`

**Purpose.** Manchester line-code decoder over an OOK envelope.

**Args.** iq_path (str), sample_rate_hz (int), symbol_rate_hz (float, required), polarity ('ieee'|'thomas', default 'ieee').

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "decode_manchester", "args": {"iq_path": "...", "sample_rate_hz": 2000000, "symbol_rate_hz": 2048.0}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Returns bits + invalid_pairs (symbol-timing errors). IEEE 802.3 polarity: 01->1, 10->0. G.E. Thomas: swap.

## `decode_pwm`

**Purpose.** Pulse-width-modulation decoder over an OOK envelope.

**Args.** iq_path (str), sample_rate_hz (int), short_us (float, required), long_us (float, required).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "decode_pwm", "args": {"iq_path": "...", "sample_rate_hz": 2000000, "short_us": 400, "long_us": 800}, "justification": "...", "expected_effect": "..."}
```

**Notes.** 0 = short pulse, 1 = long pulse. Returns bits + pulse_widths_us + invalid_pulses.

## `decode_ppm`

**Purpose.** Pulse-position-modulation decoder over an OOK envelope.

**Args.** iq_path (str), sample_rate_hz (int), pulse_us (float, required; symbol period is 2*pulse_us).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "decode_ppm", "args": {"iq_path": "...", "sample_rate_hz": 2000000, "pulse_us": 400}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Pulse in the first half of the symbol slot = 1; second half = 0.

## `decode_nrz`

**Purpose.** NRZ / NRZI line-code decoder.

**Args.** iq_path (str), sample_rate_hz (int), symbol_rate_hz (float, required), variant ('nrz'|'nrzi', default 'nrz'), inverted (bool, default false).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "decode_nrz", "args": {"iq_path": "...", "sample_rate_hz": 2000000, "symbol_rate_hz": 9600}, "justification": "...", "expected_effect": "..."}
```

**Notes.** 'nrz' = level encodes bit directly; 'nrzi' = transition encodes a 1.

## `decode_pocsag`

**Purpose.** POCSAG paging decoder (baud 512/1200/2400).

**Args.** iq_path (str), sample_rate_hz (int), baud (int in {512, 1200, 2400}, default 1200).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "decode_pocsag", "args": {"iq_path": "...", "sample_rate_hz": 2000000, "baud": 1200}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Returns per-message ric, function, and both numeric-BCD and 7-bit-ASCII payload strings. Also reports sync-word offsets and per-codeword BCH validity.

## `decode_ads_b`

**Purpose.** Mode S / ADS-B decoder for 1090 MHz captures.

**Args.** iq_path (str), sample_rate_hz (int, >= 2000000), max_frames (int, default 64).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "decode_ads_b", "args": {"iq_path": "...", "sample_rate_hz": 2000000}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Read-only over already-captured IQ. TX on 1090 MHz stays BLOCKED regardless. Returns per-frame df, icao24_hex, raw_hex, crc_ok.

## `decode_rtty`

**Purpose.** RTTY / Baudot ITA2 decoder over a 2FSK envelope.

**Args.** iq_path (str), sample_rate_hz (int), baud (float, default 45.45), invert (bool, default false).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "decode_rtty", "args": {"iq_path": "...", "sample_rate_hz": 2000000, "baud": 45.45}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Returns decoded text (with LTRS/FIGS shift-state tracking) plus framing_errors count. Try invert=true if the decoded text is nonsense but num_characters is nonzero — some transmitters swap MARK/SPACE polarity.

## `decode_ax25`

**Purpose.** AX.25 packet-radio decoder (HDLC over Bell 202 AFSK-1200 or direct FSK-9600).

**Args.** iq_path (str), sample_rate_hz (int), baud (float, default 1200), invert (bool, default false).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "decode_ax25", "args": {"iq_path": "...", "sample_rate_hz": 48000, "baud": 1200}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Returns per-frame destination/source/digipeaters, control, PID, info bytes, and CRC-16-CCITT status. NRZI + bit-unstuffing handled internally.

## `decode_aprs`

**Purpose.** APRS decoder - AX.25 UI frames with APRS payload interpretation.

**Args.** iq_path (str), sample_rate_hz (int), baud (float, default 1200), invert (bool, default false).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "decode_aprs", "args": {"iq_path": "...", "sample_rate_hz": 48000}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Recognized DTIs: !/= (position no-ts), //@  (position ts), > (status), : (message), ; (object), T (telemetry). Position reports return lat/lon in decimal degrees.

## `knowledge_list_topics`

**Purpose.** Enumerate every topic dir under knowledge/ and its markdown files.

**Args.** No arguments.

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_list_topics", "args": {}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Read-only; reads from disk under knowledge/. Never touches libhackrf.

## `knowledge_read`

**Purpose.** Return the contents of one markdown file under knowledge/<topic>/.

**Args.** topic (str, e.g. 'dsp'), name (str, e.g. 'README.md').

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_read", "args": {"topic": "dsp", "name": "reference.md"}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Path-traversal-safe (topic/name matched against safe-name regexes). 1 MB per-file cap. Only .md files are readable via this verb; records/*.json is exposed via knowledge_lookup_* verbs.

## `knowledge_search`

**Purpose.** Case-insensitive substring search across every corpus markdown file.

**Args.** query (str), max_results (int, default 20, 1-200).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_search", "args": {"query": "Manchester", "max_results": 10}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Prefer a knowledge_lookup_* verb when a typed lookup fits the question.

## `knowledge_lookup_band`

**Purpose.** Return the bands.json record(s) covering freq_hz.

**Args.** freq_hz (int, 1 Hz-6 GHz).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_lookup_band", "args": {"freq_hz": 433920000}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Multiple matches are possible where allocations overlap (e.g. EU ISM 433 sits inside US amateur 70 cm).

## `knowledge_lookup_modulation`

**Purpose.** Return the modulations.json record for a named modulation family.

**Args.** name (str, e.g. 'OOK', 'GFSK', '2FSK', 'LoRa').

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_lookup_modulation", "args": {"name": "GFSK"}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Matches on name, id, or aliases (case-insensitive). Returns null when no record matches.

## `knowledge_lookup_protocol`

**Purpose.** Return the protocols.json record for a named protocol.

**Args.** name (str, e.g. 'POCSAG', 'ADS-B', 'AX.25', 'LoRaWAN').

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_lookup_protocol", "args": {"name": "POCSAG"}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Matches on name, id, or aliases (case-insensitive). Returns null when no record matches.

## `knowledge_lookup_keyfob`

**Purpose.** Return keyfob-system records matching vendor and/or model.

**Args.** vendor (str, optional), model (str, optional). At least one must be provided.

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_lookup_keyfob", "args": {"vendor": "Chamberlain"}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Substring matches, case-insensitive. Returns every matching record; the caller picks the closest generation.

## `knowledge_lookup_decoder`

**Purpose.** Return the decoders.json record for a named decoder family.

**Args.** name (str, e.g. 'Manchester', 'NRZ', 'PWM', 'PPM').

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_lookup_decoder", "args": {"name": "Manchester"}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Each record links to the paired analyze_iq_* / decode_* verb via tools_downstream.

## `knowledge_bibliography`

**Purpose.** Return one bibliography citation by id, or the full list.

**Args.** cite_id (str, optional). Omit to list every citation.

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_bibliography", "args": {"cite_id": "fcc-part-15"}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Returns an empty list when cite_id has no match.

## `knowledge_random`

**Purpose.** Return one random markdown file from the corpus.

**Args.** seed (int, optional) for deterministic selection.

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_random", "args": {}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Uses SystemRandom when seed is unset; the same seed always picks the same file.

## `knowledge_explain_signal`

**Purpose.** Rank candidate signals from known_signals.json given hints.

**Args.** freq_hz (int, optional), bw_hz (int, optional), modulation_guess (str, optional), max_results (int, default 5). At least one hint required.

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_explain_signal", "args": {"freq_hz": 433920000, "modulation_guess": "OOK"}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Score is the sum of matched hints (each contributes 1.0). Ties broken by record id.

## `knowledge_cross_reference`

**Purpose.** Traverse see_also across every records/*.json file.

**Args.** record_id (str, e.g. 'protocol-pocsag-1200').

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_cross_reference", "args": {"record_id": "protocol-pocsag-1200"}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Returns {record, related, unresolved}. unresolved holds ids that no records file exports.

## `knowledge_verify_claim`

**Purpose.** Grade a factual claim against the trap catalog.

**Args.** text (str, 1-1000 chars).

**Default risk tier.** LOW

**Example envelope.**

```json
{"action": "knowledge_verify_claim", "args": {"text": "The HackRF can transmit on ADS-B."}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Returns verdict in {true, false, needs_qualification, unverified} with citations. 'unverified' means no trap fired — caveat accordingly.

## `play_sequence`

**Purpose.** Chain 2-8 sub-actions through the funnel in order.

**Args.** steps (list of {action, args}, 2-8 items), stop_on_error (bool, default true).

**Default risk tier.** LOW (per-step risk applies)

**Example envelope.**

```json
{"action": "play_sequence", "args": {"steps": [{"action": "analyze_iq_modulation", "args": {"iq_path": "..."}}, {"action": "analyze_iq_symbols", "args": {"iq_path": "..."}}]}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Each sub-action re-enters CommandExecutor.execute() with its own risk assessment, permission check, approval flow, and audit trail. No batching bypass. play_sequence cannot nest inside itself. stop_on_error=false runs every step even after a failure.

## `sweep_spectrum_bulk`

**Purpose.** Sweep multiple bands in one call (2-8 ranges).

**Args.** ranges (list of {start_freq_hz, end_freq_hz}, length 2-8), sample_rate_hz (int, default 2000000), lna_gain_db (int, default 16), vga_gain_db (int, default 20), rf_amp_db (int, default 0), dwell_s (float, default 1.0), fft_size (int, default 4096). Shared across all ranges.

**Default risk tier.** LOW at dwell_s <= 2s; MEDIUM above

**Example envelope.**

```json
{"action": "sweep_spectrum_bulk", "args": {"ranges": [{"start_freq_hz": 315000000, "end_freq_hz": 316000000}, {"start_freq_hz": 433000000, "end_freq_hz": 435000000}]}, "justification": "...", "expected_effect": "..."}
```

**Notes.** Returns {num_ranges, sweeps} where each sweep entry has the same shape as sweep_spectrum's result. Per-range risk classification applies at the driver level.

