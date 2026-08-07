# Changelog

## Unreleased

### Added

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
  depth. See `plan-organization.md` and `plan-knowledge.md`.
- `skills/hackrf/SKILL.md` — assistant guidance for when + how to
  reach the MCP.
- `docs/rf_cheatsheet.md`, `docs/ctf_playbook.md` — quick-reference
  placeholders.

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
