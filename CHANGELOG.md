# Changelog

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
