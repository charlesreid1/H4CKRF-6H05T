# Changelog

## Unreleased

### Added

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
