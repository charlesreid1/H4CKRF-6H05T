# Changelog

## Unreleased

### Last-mile pass (CTF readiness)

**Group A — plan-file references purged.** Every `plan-*.md` link
removed from the shipped surface (Readme, CHANGELOG, docs/,
knowledge/, scripts/, src/, tests/). Replaced with self-contained
statements or pointers to `docs/architecture.md` and
`knowledge/MANIFEST.md`. `attic/README.md` documents that
directory as the archive for historical build plans.

**Group B — docs match code.** `docs/architecture.md` and
`docs/mcp.md` no longer describe the knowledge tier as
`[planned]` — it exists. `docs/mcp.md` tools table now
auto-generates from `CommandAction` (grouped Know / Analyze /
Act / Compose); the generator gains a `--check` mode for CI drift
detection. `docs/development.md` project layout tree refreshed to
match the current `src/` and `tests/` (adds MCP, analysis, capture
budget, lore/mcp CLI). `(Part N)` scaffolding stripped throughout.

**Group C — placeholders removed.** `DECODE_OOK` deleted from the
surface (breaking); callers switch to `decode_manchester` /
`decode_nrz`. `Skeleton — Tier N` markers removed from 25
knowledge READMEs. `(planned)`, `not yet implemented`, `deferred`
prose fixed to reflect the current verb set. Driver docstring on
`transmit_iq` no longer claims it's "not CLI-exposed" (it is —
via chat and via the MCP tool). `_handle_play_sequence`
docstring re-labels itself as a defence-in-depth guard rather
than a stub.

**Group D — safety hardening.** `AuditService.rotate(keep_days)` +
`AuditService.stats()` + `hackrf-agent audit rotate|stats` CLI
verbs; `ROTATED` event type. `MAX_TX_SECONDS` env var for
session-level cumulative TX budget (mirrors the capture budget).
`sweep_spectrum_bulk` aggregate-cost cap (`n_ranges * dwell_s >
30 s` → MEDIUM). `hackrf-agent grant revoke-all` CLI verb.
`hackrf-agent doctor --strict` pre-flight (pyhackrf importable,
firmware line, corpus discoverable, records validate, audit DB
size). API-key check downgraded to soft warning under the default
doctor. Driver-lock release regression test.

**Group E — capability polish.** POCSAG sync-word search
vectorised via `sliding_window_view`; both polarities folded into
one pass. `sweep_spectrum` surfaces a `truncated` flag when
requested span exceeds `sample_rate_hz`. Every `capture_iq` writes
a SigMF sidecar (`.sigmf-meta`) so URH / Inspectrum / gqrx can
open the file without hand-configured metadata.

**Group F — regression guardrails.** `test_no_placeholders.py`
greps the shipped surface for drift phrases (placeholder / TODO /
`[planned]` / `Skeleton — Tier` / `plan-*`) — every hit is a bug.
`test_doc_freshness.py` asserts every `CommandAction` is
enumerated in the auto-generated docs. `test_corpus_records_valid.py`
runs the corpus validator; pre-commit hook does the same on any
records-file change. Ruff config ratcheted to include RUF; ruff
auto-fix pass cleaned 56 findings; per-file ignores catalogue the
pre-existing tail.

### Added

- **`MAX_CAPTURE_MINUTES` env var** — session-level cumulative-capture
  budget. When set to a positive number, the sum of every
  `capture_iq`'s `duration_s` in the session must stay under that
  cap; a call that would push the total over is refused with
  `BLOCKED` before any RF activity. Belt-and-suspenders to the
  per-command duration limits.
- **`sweep_spectrum_bulk` verb.** Sweep 2-8 bands in one call.
  Shared sample_rate/gain/dwell/fft_size across ranges. Simpler
  than a play_sequence-of-sweeps when the ranges are known
  up-front. Per-range risk classification applies.
- **`play_sequence` verb.** Chain 2-8 sub-actions through the
  funnel in order. Each sub-action re-enters `CommandExecutor.
  execute()` with its own trace_id, risk assessment, permission
  check, approval flow, and audit trail. No batching bypass.
  Cannot nest inside itself. `play_sequence` itself is LOW.
- **`analyze_iq_carrier_frequency` verb.** Refines the actual
  carrier-frequency offset in a captured .iq file via
  parabolic-interpolated FFT peak. Useful for unlocking a decoder
  that assumed the wrong offset.
- **Seven additional knowledge-tier verbs** — `knowledge_lookup_protocol`,
  `knowledge_lookup_keyfob`, `knowledge_lookup_decoder`,
  `knowledge_bibliography`, `knowledge_random`, `knowledge_explain_signal`,
  `knowledge_cross_reference`. All hardcoded LOW. `explain_signal` scores
  candidates in `known_signals.json` against a `(freq_hz, bw_hz,
  modulation_guess)` hint tuple; `cross_reference` walks `see_also`
  across every records/*.json file with resolved-vs-unresolved
  reporting. Lookup matcher upgraded to exact-then-substring so short
  aliases like `POCSAG` resolve without demanding the full record name.
- **Three new records files.** `records/decoders.json` (Manchester,
  differential Manchester, NRZ, NRZI, PWM, PPM, PCM),
  `records/sdr_hardware.json` (HackRF One + RTL-SDR v3 / Airspy R2 /
  LimeSDR Mini / USRP B200 / ADALM-Pluto / KrakenSDR comparative
  entries), and `records/regulatory.json` (documentation-only mirror
  of the hardcoded BLOCKED/ISM tables in `frequency_policy.py` — the
  gate does not read it).
- **Reviewer's checklist for adding a `CommandAction`.** The 10-item
  short list in `docs/development.md` becomes a 14-item authoritative
  checklist: enum → args → risk → handler → executor pass-through →
  MCP tool → prompt → schema regen → unit test → handler test → MCP
  registry test → integration test (if applicable) → CHANGELOG →
  no-pyhackrf-outside-`hw/` guard. Includes corpus-side additions
  and decoder-specific guidance (round-trip synthesized-signal tests
  + `records/protocols.json` updates).
- **SKILL.md refreshed** with all 20 new verbs organized into three
  tiers (Know / Analyze / Act). Adds explicit corpus-depth cues and
  a playbook mirroring `docs/ctf_playbook.md`.
- **Tier-2 corpus topics (14 topics).** ISM 315/433/868-915/2400,
  ADS-B, POCSAG/FLEX, keyfobs (with full attack model), garage-doors,
  weather-stations, TPMS, LoRa, Zigbee/802.15.4, DMR, TETRA, P25,
  airband, marine VHF/AIS, satellite, APRS. Backing records:
  `protocols.json` (15 records), `keyfobs.json` (9), and
  `known_signals.json` (9 canonical signatures).
- **RTTY, AX.25, and APRS decoders.** Three new LOW-risk verbs.
  - `decode_rtty`: Baudot ITA2 5-bit over 2FSK with LTRS/FIGS shift
    tracking, framing = 1 start + 5 data + 1 stop.
  - `decode_ax25`: HDLC over Bell 202 AFSK-1200 (or direct FSK-9600).
    NRZI + bit-unstuffing + LSB-first packing + CRC-16-CCITT FCS.
    Parses destination/source/digipeaters, control, PID, info.
  - `decode_aprs`: interprets AX.25 UI frames as APRS. Supports
    position (uncompressed, w/ + w/o timestamp), status, message,
    object, and telemetry data-type identifiers.
  - Extracted a shared `fsk_bit_stream` DSP primitive used by POCSAG,
    RTTY, and AX.25. Switched the threshold logic from median (which
    fails on idle-mark-heavy streams like RTTY) to a per-symbol min/max
    midpoint.
- **Protocol decoders — `decode_pocsag` and `decode_ads_b`.** Both LOW
  risk, both read-only. POCSAG: 2FSK demod, sync-word scan for
  `0x7CD215D8` in both polarities, BCH(31,21) syndrome + even-parity
  validation per codeword, address+message assembly with numeric-BCD
  and 7-bit-ASCII payload interpretations. ADS-B: Mode S 112-bit
  extended-squitter decoder with preamble correlation, 1 μs/bit PPM
  slicing, CRC-24 (`0xFFF409`), DF+ICAO24 extraction. Requires
  `sample_rate_hz >= 2 MHz`. **TX on 1090 MHz remains BLOCKED** — this
  verb only decodes captured RX data.
- **Analysis tier — seven new `CommandAction` verbs.** Offline DSP on
  already-captured `.iq` files, hardcoded `LOW` risk. Verbs:
  `analyze_iq_modulation` (moment-based classifier),
  `analyze_iq_symbols` (edge-interval symbol-rate estimator),
  `analyze_iq_spectrogram` (compact per-slice peak-frequency + power
  summary; never the full FFT matrix), `decode_manchester`,
  `decode_pwm`, `decode_ppm`, `decode_nrz` (with NRZI variant).
  Handlers refuse `iq_path` outside session root; no `pyhackrf` import.
- New DSP module `hackrf_agent.hw.analysis` — `load_iq_file` (1 GiB
  cap), `classify_modulation`, `estimate_symbol_rate`,
  `spectrogram_summary`, plus line-code decoders sharing a `slice_ook`
  pipeline.
- **Knowledge tier — six new `CommandAction` verbs.** Read-only corpus
  access, hardcoded `LOW` risk, funnels through the existing
  `CommandExecutor` chokepoint. Verbs: `knowledge_list_topics`,
  `knowledge_read`, `knowledge_search`, `knowledge_lookup_band`,
  `knowledge_lookup_modulation`, `knowledge_verify_claim`. Backed by the
  on-disk corpus at `knowledge/` (Tier-1 topics + `bands.json`,
  `modulations.json`, `iq_formats.json`, `bibliography.json` seeded).
- New module `hackrf_agent.domain.knowledge` — `KnowledgePaths` with
  path-traversal-safe resolvers, plus pure functions for corpus reads and
  record lookups. Discovers the corpus via `HACKRF_KNOWLEDGE_DIR` env
  var or an upward walk to `knowledge/MANIFEST.md`.
- `knowledge/` corpus scaffolding: 30 topic dirs (Tier 1-4) with
  README.md stubs; Tier-1 topics `dsp/`, `sdr-fundamentals/`,
  `modulation/`, `hackrf-hardware/`, `iq-formats/`, `regulatory/`
  authored to full `reference.md` / `walkthrough.md` / `recognition.md`
  depth.
- `skills/hackrf/SKILL.md` — assistant guidance for when + how to
  reach the MCP.
- `docs/rf_cheatsheet.md`, `docs/ctf_playbook.md` — quick-reference
  guides.

## v0.1.0 (unreleased)

Initial release. Eight-Part implementation complete:

- **Part 1:** Environment, hardware access, reference material.
- **Part 2:** Data contracts (models, enums) and policy tables (frequency_policy, risk_assessor).
- **Part 3:** Persistence layer (SQLite-backed AuditService, PermissionService).
- **Part 4:** Hardware driver (pyhackrf wrapper) and DSP primitives.
- **Part 5:** CommandExecutor — the single chokepoint every action passes through.
- **Part 6:** LLM integration (OpenRouterClient, HackrfAgent conversation loop, system prompt).
- **Part 7:** CLI (Typer), approval UX, kill switch.
- **Part 8:** Testing strategy (three tiers, two orthogonal markers, 26+ new tests), CI
  workflows (every-push, nightly LLM, manual hardware), pre-commit gates, and
  documentation (architecture, safety, development, CLI, AI package, tests).
