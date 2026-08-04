# Test Suite

How to run and understand the `hackrf-agent` tests.

---

## How to Run

### Every-push tier (no hardware, no API key)

```bash
pytest tests/unit/ tests/integration/ tests/e2e/ -q -m "not hardware and not llm"
```

This runs everything that doesn't need a HackRF or live LLM. These tests are fast,
deterministic, and run in CI on every push. **~420 tests, ~10 seconds.**

### Individual tiers

```bash
pytest tests/unit/                       # Pure logic — no I/O
pytest tests/integration/ tests/e2e/ -q  # Fakes for hardware + LLM
```

### Opt-in markers

```bash
pytest --hardware -m hardware            # Requires HackRF One attached via USB
pytest --llm -m llm                      # Requires ANTHROPIC_API_KEY
```

### Snapshot update mode

```bash
UPDATE_SNAPSHOTS=1 pytest tests/e2e/test_keyfob_workflow.py
```

This regenerates the committed audit snapshot. Review the diff before committing.

---

## What the Tiers Mean

### Unit (`tests/unit/`)

No hardware, no network, no LLM, no filesystem I/O (SQLite `:memory:` is allowed).
These test pure functions and classes in isolation:

- **Domain models** (`test_models.py`) — Pydantic validation, enum exhaustiveness.
- **Frequency policy** (`test_frequency_policy.py`) — every band, boundary conditions, off-by-one on band edges.
- **Risk assessor** (`test_risk_assessor.py`) — matrix of `(CommandAction, band, grant-state) → RiskLevel`. This is the safety net.
- **DSP** (`test_dsp.py`) — synthetic-signal peak recovery, noise-floor estimator sanity.
- **Handlers** (`test_handlers.py`) — handler dispatch with fake driver, arg extraction, path validation.
- **Result formatter** (`test_result_formatter.py`) — no raw IQ ever appears in the output dict.
- **Prompts** (`test_prompts.py`) — system prompt includes required sections; tool schema validates.
- **Audit service** (`test_audit_service.py`) — round-trip, concurrent writes.
- **Permission service** (`test_permission_service.py`) — grant CRUD, TTL enforcement.
- **CLI components** (`test_cli_*.py`) — parsers, settings, kill switch, approval prompts.
- **LLM client** (`test_llm_client.py`) — fakes, rate limiter, construction.
- **Conftest** (`test_conftest.py`) — marker registration, fixture behaviour.
- **Support helpers** (`test_support_helpers.py`) — FakeDriver, ScriptedLLMClient, audit snapshot.
- **Fixtures** (`test_fixtures.py`) — IQ file loading, FFT validation, sibling .md docs.
- **Schema regenerator** (`test_schema_regenerator.py`) — every action has docs, determinism, no drift.

### Integration (`tests/integration/`)

These tests wire multiple real components together but fake external dependencies:

- **No-marker** — `test_executor.py` (full funnel with FakeDriver), `test_agent_loop.py`
  (HackrfAgent with FakeLLMClient), `test_persistence_roundtrip.py`, CLI command tests.
  Run on every CI push.
- **`@pytest.mark.hardware`** — `test_hackrf_driver.py` runs `get_device_info` and a
  bounded RX sweep. Never TX. Requires `--hardware` flag.
- **`@pytest.mark.llm`** — `test_agent_live.py` runs one benign round-trip against
  real Claude. Requires `--llm` flag and `ANTHROPIC_API_KEY`.

### End-to-end (`tests/e2e/`)

Full workflow with scripted LLM + fake driver + real executor + real audit DB:

- **`test_keyfob_workflow.py`** — the "Find my car's keyfob frequency" workflow from
  `plan-bender.md`, encoded as an executable test. Asserts correct sequence of tool
  calls, approval flow, and audit trail shape.
- **`test_full_funnel_matrix.py`** — table-driven: one row per `(action, tier)`
  combination. Catches regressions where a new action's risk classification drifts.

### The three markers

The markers `hardware`, `llm`, and `slow` are **orthogonal** to the tier (unit,
integration, e2e). Unit tests never carry `hardware` or `llm`. Integration and
e2e tests may carry either.

The `tests/conftest.py` hook auto-skips `hardware`/`llm`-marked tests unless the
corresponding `--hardware`/`--llm` flag is passed.

### CI strategy

| Pipeline | Trigger | What |
|----------|---------|------|
| `tests.yml` | Every push + PR | Lint, typecheck, unit (3.11 + 3.12), integration+e2e (no markers) |
| `tests-llm.yml` | Nightly 03:00 UTC + manual | `@pytest.mark.llm` with org's `ANTHROPIC_API_KEY` secret |
| `tests-hardware.yml` | Manual dispatch only | `@pytest.mark.hardware` on self-hosted `hackrf-attached` runner |

### Snapshot philosophy

The audit snapshot at `tests/fixtures/audit/keyfob_session.json` compares
**shape, not exact values.** Timestamps, UUIDs, IQ paths, and durations vary
run-to-run — `rows_to_snapshot()` masks them. The snapshot catches regressions
in the executor's audit trail *shape* (which events fire in which order).
Value assertions belong in unit tests, not the snapshot.

### Fixture IQ files

Three `.iq` fixtures in `tests/fixtures/iq/`, each ≤ 100 KB:

| File | Content | Source |
|------|---------|--------|
| `ism_433_tone.iq` | CW tone at 434.12 MHz (200 kHz above 433.92 MHz center) | Synthetic placeholder |
| `ism_315_noise_only.iq` | Noise floor only — no transmitter | Synthetic placeholder |
| `two_tone.iq` | Two tones at ±150 kHz from 433 MHz center | Synthetic |

Each has a sibling `.iq.md` provenance file. The `two_tone.iq` can be regenerated
from `two_tone.py`. Real hardware captures should replace the synthetic placeholders
when a HackRF is available.
