# Changelog

## v0.1.0 (unreleased)

### Added

- **`analyze_pulses` action** — shells out to `rtl_433 -A` on a captured IQ
  file to estimate pulse timing, guess the modulation family
  (OOK/PPM/PWM/Manchester), and match against ~200 known device protocols.
  Requires `rtl_433` installed on the host (`brew install rtl_433`).
- **`demodulate_bits` action** — shells out to `urh_cli` with explicit demod
  parameters (modulation type, samples-per-symbol, threshold, etc.) and
  returns the raw bitstream. No protocol matching — the caller recognises
  framing, CRC, sync words. Requires URH installed (`pipx install urh`).
- **`decode_ook` → `analyze_pulses` alias** — the old action name is
  accepted as a backward-compatible alias for one release cycle. Saved
  transcripts and plans referencing `decode_ook` continue to work.
- **`doctor` three-state check status** — `Status` enum with `OK`, `WARN`
  (optional tool unavailable; exit still 0), and `FAIL` (required feature
  broken; exit 1). Added `rtl_433` and `urh_cli` checks (both `WARN` on
  absent).

### Changed

- **`doctor` output** now shows yellow `WARN` for optional-tool checks
  instead of red `FAIL`. The LLM system prompt documents the two new actions
  and the recommended `analyze_pulses` → `demodulate_bits` workflow.

### Fixed

- `docs/safety.md` incorrectly listed `decode_ook` as MEDIUM tier. Both
  `analyze_pulses` and `demodulate_bits` are correctly classified as LOW
  (read-only, file-local, no TX).

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
