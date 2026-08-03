# Test Suite

How to run, write, and understand the `hackrf-agent` tests.

---

## Quick Start

```bash
# Install dev deps (includes pytest, ruff, mypy)
source .venv/bin/activate
pip install -e ".[dev]"

# Run all unit tests
pytest tests/unit/ -q

# Run with coverage
pytest tests/unit/ -q --cov=src/hackrf_agent/domain --cov-report=term-missing
```

---

## Test Tiers

| Tier | Command | What runs | Requires |
|---|---|---|---|
| **Unit** | `pytest tests/unit -q` | Pure logic — no hardware, network, LLM, or filesystem. Models, policy, risk, DSP, prompts, LLM client fakes. **240+ tests.** | Nothing |
| **Integration (safe)** | `pytest tests/integration/ -q -m "not hardware and not llm"` | Executor, agent loop, DSP pipeline, persistence roundtrip — all with fakes. **80+ tests.** | SQLite (`:memory:`) |
| **Hardware** | `pytest tests/integration --hardware -q` | HackRF attached via USB | HackRF One |
| **LLM** | `pytest tests/integration --llm -q` | One benign round-trip to Claude | `ANTHROPIC_API_KEY` |
| **End-to-end** | `pytest tests/e2e -q` | Full workflow with fake LLM + mock HW | Nothing |

Unit tests are the default and always safe. They run in CI on every push and complete
in under a second. Integration (safe) tests run on every push as well.

---

## Unit Tests: File-by-File

### `tests/unit/test_models.py` — 17 tests, 229 lines

Covers the data models and enums in `src/hackrf_agent/domain/models.py`.

| Class | Tests | What it covers |
|---|---|---|
| `TestExecuteCommand` | 5 | Construction, empty/whitespace justification rejected, `args` default factory is distinct per instance |
| `TestGrant` | 6 | Distinct UUIDs per instance, `granted_at` populated at construction, `is_active` (expired / revoked), `covers_frequency` edge-inclusive, `covers_transmission` |
| `TestCommandAction` | 1 | Exactly 8 enum values match the spec |
| `TestRiskLevel` | 1 | Four uppercase string values |
| `TestRiskAssessment` | 4 | `is_blocked` / `can_proceed` true/false across all four `RiskLevel` values |

**Key guardrails tested here:**

- **Mutable default bug:** `Field(default_factory=dict)` — two `ExecuteCommand` instances
  get distinct `args` dicts. Modifying one does not affect the other.
- **Eval-at-import UUID bug:** `Field(default_factory=uuid4)` — two `Grant` instances get
  distinct `id` values.
- **Eval-at-import datetime bug:** `Field(default_factory=_utcnow)` — two `Grant` instances
  constructed moments apart get distinct `granted_at` values.
- **Whitespace-only strings:** `justification` and `expected_effect` reject all-whitespace
  strings via `model_validator`.

---

### `tests/unit/test_frequency_policy.py` — 37 tests, 168 lines

Covers the band tables and lookup functions in
`src/hackrf_agent/domain/frequency_policy.py`.

| Class | Tests | What it covers |
|---|---|---|
| `TestIsBlocked` | 19 | 15 blocked frequencies (ADS-B, aviation voice, GPS L1/L2, maritime, cellular, hydrogen line, radio astronomy) + 4 negative cases (ISM bands, unremarkable frequencies) |
| `TestIsInIsm` | 10 | 7 ISM frequencies (315, 433, 902, 2.4G, 5.8G, including edge boundaries) + 3 negative cases (just below/above edges) |
| `TestIsInAmateur` | 2 | 70 cm and 23 cm amateur bands |
| `TestRangeIsBlocked` | 3 | Sweep spanning ADS-B (blocked), sweep inside ISM (not blocked), sweep just below ADS-B (not blocked) |
| `TestBandInvariants` | 3 | Every tuple in `BLOCKED_BANDS`, `ISM_BANDS`, and `AMATEUR_BANDS` satisfies `start < stop` |

**Edge cases tested:**

- **Inclusive boundary:** blocked bands are tested at both lower and upper edges for
  `is_blocked`, `is_in_ism`, and `Grant.covers_frequency`.
- **Just-outside boundary:** frequencies 1 Hz below and above band edges return `False`.
- **No overlap test:** intentionally absent — VHF Guard is nested inside Aviation Voice,
  and LTE Band 17 is nested inside LTE Band 12, by design.

---

### `tests/unit/test_risk_assessor.py` — 41 tests, 548 lines

Covers the `RiskAssessor.assess()` decision tree in
`src/hackrf_agent/domain/risk_assessor.py`. This is the largest and most
important test file — every branch of the risk-tier decision tree is exercised.

| Class | Tests | What it covers |
|---|---|---|
| `TestReadOnlyActions` | 5 | `GET_DEVICE_INFO`, `GRANT_LIST`, `AUDIT_QUERY`, `READ_IQ_SUMMARY`, `DECODE_OOK` → always LOW |
| `TestSweepSpectrum` | 7 | Short dwell → LOW, long dwell → MEDIUM, dwell omitted (default 1.0), sweep crossing ADS-B/GPS L1 (RX is fine → LOW), equal start/end → BLOCKED, missing args → BLOCKED |
| `TestCaptureIq` | 9 | Short capture → LOW, 5 s boundary → LOW, long capture → MEDIUM, ADS-B/GPS L1/maritime (RX is fine), negative duration → BLOCKED, missing args → BLOCKED |
| `TestTransmitIqHardwareLimits` | 3 | Gain > 47 dB → BLOCKED, negative gain → BLOCKED, missing gain → BLOCKED |
| `TestTransmitIqBlockedBands` | 4 | TX on ADS-B, GPS L1, VHF Guard, cellular DL → all BLOCKED |
| `TestTransmitIqIsmNoGrant` | 5 | ISM with gain ≤ 30 → MEDIUM, gain 30 (boundary) → MEDIUM, gain 35/47 → HIGH, ISM edge (902 MHz) → MEDIUM |
| `TestTransmitIqWithGrants` | 4 | Grant fully covers → MEDIUM ("in-scope grant"), gain exceeds grant cap → HIGH, out-of-band → HIGH, expired grant → ISM fallback |
| `TestTransmitIqAmateur` | 3 | 70 cm → HIGH, 23 cm → HIGH, ISM 902 ∩ 33 cm amateur → MEDIUM (ISM wins) |
| `TestUnknownAction` | 1 | Defensive branch → BLOCKED (skipped: `str, Enum` rejects unknown values at construction) |

**Decision tree priority verified:**

1. Hardware/arg sanity checks (missing args, gain > 47, negative gain) — checked first
2. Blocked-band check — gates TX, does **not** gate RX
3. Active grant check — any grant covering the TX → MEDIUM
4. ISM band rules — gain ≤ 30 → MEDIUM, gain > 30 → HIGH
5. Amateur band — HIGH (licensed-operator territory)
6. Unclassified frequency — HIGH

**What is intentionally NOT tested:**

- The defensive `BLOCKED("unknown action")` branch. Python's `str, Enum` rejects unknown
  values at construction time, so this code path is unreachable via normal Pydantic flows.
  The branch remains in the source as defense-in-depth against future enum changes.

---

### `tests/unit/test_dsp.py` — 23 tests, 290 lines

Covers all five DSP primitives in `src/hackrf_agent/hw/dsp.py`. **Zero hardware required**
— every test uses synthetic signals generated via `synth_tone()`.

| Class | Tests | What it covers |
|---|---|---|
| `TestIqToComplex64` | 5 | Zero-bytes→zero-array, odd-length→`ValueError`, fullscale ±127→±1.0, rejects non-int8 dtype, accepts bytearray and memoryview |
| `TestFftMagnitudeDb` | 8 | Tone lands in correct bin (±2 bin width), non-power-of-two→`ValueError`, too-short input→`ValueError`, unknown window→`ValueError`, fft_size edge min (64) and max (65536), fft_size below min (32)→error, blackman-harris and rect windows accepted |
| `TestFftFreqAxis` | 1 | First/last/mid elements match expected center±rate/2 formula |
| `TestEstimateNoiseFloor` | 3 | Pure noise floor within ±3 dB of true, empty spectrum→`ValueError`, strong tone does not skew median-of-lower-half estimator |
| `TestFindPeaks` | 6 | Two well-separated tones→2 peaks at correct bins, `top_n=1` returns only stronger tone, pure noise→empty list (prominence_db=30), min_bin_gap deduplication, mismatched shape→`ValueError`, `Peak` dataclass fields populated |

**Key guardrails tested here:**

- **int8 scaling:** dividing by 127 (not 128) places 0 dBFS at true fullscale. Test 3
  verifies ±127→±1.0 exactly.
- **Window normalization:** window divided by its mean so a full-scale sinusoid
  measures 0 dBFS. Not tested as an absolute value (the plan warns this is brittle) —
  instead tested as relative peak position accuracy.
- **Peak prominence:** the `prominence_db=30.0` pure-noise test is deliberately
  aggressive — if pure noise ever produces a peak 30 dB above the median-of-lower-half
  floor, something is wrong with the estimator or the FFT.

**What is intentionally NOT tested:**

- Absolute dBFS values from `fft_magnitude_db`. Window normalization is delicate and
  the test becomes brittle when tied to specific numbers. Relative behaviour (peak
  position, peak count) is the reliable signal.
- `scipy.signal.find_peaks` equivalence. The plan explicitly chooses a hand-rolled
  peak detector to avoid the scipy dependency.

---

### `tests/unit/test_hackrf_subprocess.py` — 14 tests, 158 lines

Covers the subprocess escape hatch in `src/hackrf_agent/hw/hackrf_subprocess.py`.
**All child processes are mocked** — never launches a real `hackrf_*` binary in unit
tests. Uses `patch("asyncio.create_subprocess_exec", ...)` with `AsyncMock` stubs.

| Class | Tests | What it covers |
|---|---|---|
| `TestArgvValidation` | 6 | Empty argv→`InvalidHackrfArgError`, tool not in allowlist (`rm`), newline in arg, null byte in arg, carriage return in arg, non-string element |
| `TestHappyPath` | 4 | `hackrf_info` returns `SubprocessResult` with decoded stdout, `hackrf_sweep -1 -f 433:434` passes argv through intact, `hackrf_transfer` and `hackrf_spiflash` are in the allowlist |
| `TestErrorPaths` | 4 | Non-zero exit→`HackrfError` with stderr content, timeout→`HackrfTimeoutError` (verifies `terminate()` was called), `FileNotFoundError`→`InvalidHackrfArgError` with PATH hint, stderr truncated to ~400 chars in error message |

**Key guardrails tested here:**

- **Allowlist enforcement:** `_ALLOWED_TOOLS` is a `frozenset` of exactly four
  executables (`hackrf_info`, `hackrf_sweep`, `hackrf_transfer`, `hackrf_spiflash`).
  Any argv[0] outside this set is rejected before `Popen`.
- **Control character rejection:** `\n`, `\r`, `\x00` in any argv element → rejected.
  This is belt-and-braces — the executor should never pass these, but the subprocess
  module doesn't trust its caller.
- **Timeout handling:** `asyncio.wait_for` raises `TimeoutError` → `proc.terminate()`
  → 2 s grace → `proc.kill()` → `HackrfTimeoutError`. The test verifies `terminate()`
  was called by asserting on the mock.

---

### `tests/unit/test_hackrf_driver.py` — 29 tests, 210 lines

Covers validation logic and importability of `src/hackrf_agent/hw/hackrf_driver.py`.
**No device is ever opened** — tests exercise the validation helpers, the constructor,
the lazy-import guard, and the kill-switch mechanism without touching libhackrf.

| Class | Tests | What it covers |
|---|---|---|
| `TestValidateCenterFreq` | 5 | Below min (500 kHz)→error, above max (7 GHz)→error, valid ISM (433.92 MHz)→ok, edge min (1 MHz)→ok, edge max (6 GHz)→ok |
| `TestValidateSampleRate` | 3 + 7 parametrized | Off-grid (3 Msps)→error, all 7 valid rates→ok (parametrized), zero rate→error |
| `TestValidateGain` | 8 | LNA off-grid (3 dB)→error, LNA on-grid (16/40 dB)→ok, TX VGA above max (48 dB)→error, TX VGA zero→ok, RF amp off-grid (7 dB)→error, RF amp on-grid (14 dB)→ok, RX VGA off-grid (3 dB)→error |
| `TestImportWithoutPyhackrf` | 4 | Module symbols present without pyhackrf, constructor succeeds without device, `__aenter__` without pyhackrf→`HackrfNotFoundError`, `__aexit__` with device=None is safe no-op |
| `TestKillSwitch` | 3 | `_check_stop` raises `KillSwitchTriggered` when event set, `_check_stop` no-op when clear, `get_device_info` checks stop before device-open check |

**Key guardrails tested here:**

- **Exact-grid validation:** gain values are NOT clamped or rounded. Off-grid values
  raise `InvalidHackrfArgError`. This catches caller bugs rather than silently masking
  them.
- **Lazy import guard:** the module must be importable on a machine without pyhackrf.
  Tests 1–2 in `TestImportWithoutPyhackrf` verify the symbols resolve; tests 3–4
  simulate `ImportError` inside `__aenter__` by patching `builtins.__import__`.
- **Kill-switch ordering:** `_check_stop()` is called **before** the "device not
  opened" check in every public method. Test 3 in `TestKillSwitch` verifies that a
  set stop event raises `KillSwitchTriggered`, not `HackrfError("device not opened")`.

**What is intentionally NOT tested in unit tests:**

- `run_in_executor` dispatch. The executor-thread logic is exercised in the hardware
  integration tests (`@pytest.mark.hardware`).
- pyhackrf API call shapes. These are deferred to the hardware tier — the unit tests
  never touch the real pyhackrf module.

---

### `tests/integration/test_dsp_pipeline.py` — 2 tests, 88 lines

End-to-end DSP pipeline tests. **No hardware, no pyhackrf.** Runs in every CI push.

| Test | What it covers |
|---|---|
| `test_synthetic_tone_recovery_end_to_end` | 433.925 MHz tone → int8 quantization → `iq_to_complex64` → `fft_magnitude_db` → `fft_freq_axis` → `find_peaks` → peak at 433.925 MHz ± 2 bins |
| `test_stronger_tone_at_different_offset` | Same pipeline, 915 MHz center, -200 kHz offset, fft_size=8192 |

**This is the day-1 canary.** If either test starts failing, someone changed one of
`iq_to_complex64` / `fft_magnitude_db` / `fft_freq_axis` / `find_peaks` in a way
that broke the pipeline shape. The tests simulate the full libhackrf signal chain:
complex64 synthesis → int8 quantization (matching libhackrf's signed 8-bit I/Q
interleave) → raw bytes → DSP → peak detection.

---

### `tests/integration/test_hackrf_driver.py` — 3 tests, 98 lines

Hardware integration tests. All marked `@pytest.mark.hardware` — **skipped by default**
unless `pytest --hardware` is passed. Requires a HackRF One plugged in via USB.

| Test | What it covers |
|---|---|
| `test_get_device_info` | Opens device, reads serial/firmware/board_revision — asserts non-empty strings |
| `test_sweep_spectrum_returns_expected_shape` | 100 ms sweep of 433–434 MHz ISM band at 2 Msps — asserts (4096,) float32 magnitude + (4096,) float64 freq axis |
| `test_kill_switch_aborts_sweep` | Starts a 5 s sweep in a background task, fires `stop_event.set()` after 100 ms, asserts `KillSwitchTriggered` within 2 s |

**Never TX in hardware tests.** No `transmit_iq` in CI, ever. Manual smoke testing of
TX is the operator's job (Part 8 runbook), not automation's.

---

### `tests/unit/test_llm_client.py` — 23 tests, ~340 lines

Covers the LLM client protocol, `AnthropicClient` construction, rate limiter, and
test doubles in `src/hackrf_agent/ai/llm_client.py`. **None of these tests call
the real Anthropic API.**

| Class | Tests | What it covers |
|---|---|---|
| `TestFakeLLMClient` | 4 | FIFO response ordering, call recording for assertions, empty queue→`IndexError`, non-mutation of input args |
| `TestMakeTextResponse` | 3 | `content[0].type=="text"` + `stop_reason=="end_turn"`, custom stop_reason, `raw=None` |
| `TestMakeToolUseResponse` | 4 | `stop_reason=="tool_use"` + correct `name` and `input`, preamble text prepended, default `toolu_test_1` id, custom id |
| `TestAnthropicClientConstruction` | 5 | No API key→`RuntimeError`, constructor arg takes precedence over env var, env var fallback, custom model string, missing `anthropic` package→`RuntimeError` |
| `TestRateLimiter` | 3 | 30 timestamps → 31st call sleeps (monkeypatched clock advances after sleep), 30 old timestamps → returns immediately with no sleep, mix of old+recent → old popped, recent remain |
| `TestFakeContentBlock` | 2 | Text block has `.type`/`.text` with `None` tool fields, tool_use block has `.name`/`.input`/`.id` with `None` text |
| `TestLLMResponse` | 2 | Frozen dataclass (immutable — `AttributeError` on mutation), `raw` stores arbitrary object reference |

**Key guardrails tested here:**

- **Rate limiter correctness:** `_wait_for_slot` blocks when the deque is full of recent
  timestamps and returns immediately when all timestamps are outside the 60 s window.
  The `test_blocks_at_limit` test monkeypatches `time.monotonic` to advance after each
  `asyncio.sleep` call, preventing infinite loops.
- **API key isolation:** `AnthropicClient` never reads from disk or keyring — only the
  constructor arg or the `ANTHROPIC_API_KEY` env var. Tests verify both paths.
- **Lazy import:** `anthropic` is imported only inside `AnthropicClient.__init__`,
  keeping `FakeLLMClient` and response helpers importable without the SDK installed.

**What is intentionally NOT tested here:**

- The actual `send()` round-trip. That's the `@pytest.mark.llm` job (see
  `test_agent_live.py` below).
- Concurrent rate-limiter fairness. The agent loop is single-consumer; the docstring
  documents the assumption.

---

### `tests/unit/test_prompts.py` — 19 tests, ~190 lines

Covers the system prompt content and tool schema in
`src/hackrf_agent/ai/prompts.py`. **Pure data, zero I/O.**

| Class | Tests | What it covers |
|---|---|---|
| `TestSystemPrompt` | 7 | All 6 required sections present (ISM bands, BLOCKED, execute_command, sweep-before-capture, one-tool-call-per-response), all 4 risk tiers referenced, no datetime interpolation, no UUID/per-run markers, key frequency band entries, blocked band references, version constant pattern |
| `TestToolSchema` | 10 | Tool name is `"execute_command"`, required fields (`action`, `justification`, `expected_effect`), action enum matches all `CommandAction` values (resolved via `$defs`), enum values are string values not enum names, deterministic `json.dumps`, stable across `importlib.reload`, non-empty description, top-level type is `"object"`, all Pydantic `title` fields stripped |
| `TestConstants` | 3 | `MAX_TOOL_CALLS_PER_RESPONSE == 1`, `TOOL_NAME == "execute_command"`, `SYSTEM_PROMPT` is non-empty and >1000 chars |

**Key guardrails tested here:**

- **Schema stability across imports:** `EXECUTE_COMMAND_TOOL_SCHEMA` is generated once at
  import time and must be identical on reimport — test 6 (`json.dumps` deterministic) +
  test 7 (`importlib.reload` equality) verify this.
- **Pydantic v2 `$defs` handling:** The action field's enum values are stored under
  `$defs/CommandAction` (Pydantic v2 uses `$ref` for typed enums). The test `_get_action_enum`
  helper resolves the `$ref` path. This also confirms `_strip_titles` didn't accidentally
  strip `$defs`.
- **No runtime interpolation:** The `SYSTEM_PROMPT` is a literal triple-quoted string.
  Test 2 asserts no ISO-8601 datetimes (the version constant uses `YYYY-MM-DD-vN` without
  a `T` separator). Test 3 asserts no UUID patterns.

---

### `tests/integration/test_agent_loop.py` — 23 tests, ~460 lines

Full agent-loop integration tests. **All use `FakeLLMClient`** with a real
`CommandExecutor` backed by a `FakeDriver`. The audit DB is touched, hence "integration."
Tests cover all 16 plan-specified cases plus 7 additional edge cases.

**Fixture (`bench`):** Creates a `HackrfAgent` wired to `FakeLLMClient` + `FakeDriver` +
real `CommandExecutor` + real `PermissionService` + real `AuditService`. All state is
isolated in `tmp_path`. The `FakeApprovalPort` answers `True` by default.

| Class | # | What it covers |
|---|---|---|
| `TestSimpleTextTurn` | 1 | Single text response → `AssistantText` then `TurnEnded(end_turn)` |
| `TestSingleToolCall` | 2 | `tool_use(get_device_info)` → `ToolCallStarted` + `ToolCallCompleted` + `TurnEnded`; driver called once |
| `TestChainedToolCalls` | 3 | Two sequential tool_use responses → two `ToolCallStarted`/`ToolCallCompleted` pairs |
| `TestMultipleToolUseBlocks` | 4 | Two tool_use blocks in one response → only first executed, warning logged via `caplog` |
| `TestRefusal` | 5 | `stop_reason=="refusal"` → `TurnEnded(refusal)`, no tool calls attempted |
| `TestWrongToolName` | 6 | Tool name `"not_execute_command"` → `AgentError(recoverable=True)` + `tool_result(is_error=True)`, loop continues |
| `TestMalformedToolInput` | 7 | Missing `justification` → recoverable error; bad action enum value → recoverable error |
| `TestBlockedAction` | 8 | `transmit_iq` at 1090 MHz → `ToolCallCompleted` with `success=False, message.startswith("Action blocked")`, driver NOT called |
| `TestGrantInjection` | 9, 10 | Active grant → mid-conversation `{"role":"system"}` message with grant details; no grants → no system message |
| `TestHistoryTrimming` | 11 | 30+ messages → request trimmed to ≤ `MAX_HISTORY_MESSAGES` (24) |
| `TestPairSafety` | 12 | Orphaned `tool_result` (assistant parent trimmed) → dropped from request |
| `TestRunawayProtection` | 13 | 25 queued tool_use responses → stops at 20 with `AgentError(recoverable=False, "cap")` |
| `TestMidConvSystemFallback` | 14 | Mid-conv system rejection → fallback to `<system-reminder>`, `_supports_mid_conv_system` flipped to `False`; subsequent calls use `<system-reminder>` injection |
| `TestSystemPromptAndTools` | 15, 16 | Every request includes `SYSTEM_PROMPT` with `cache_control`, `[EXECUTE_COMMAND_TOOL_SCHEMA]` as sole tool; verified across multiple calls in a turn |
| `TestUnexpectedStopReason` | — | `stop_reason=="max_tokens"` → `AgentError(recoverable=False)` |
| `TestToolUseNoBlocks` | — | `stop_reason=="tool_use"` with zero tool_use blocks → `AgentError(recoverable=False, "no tool_use blocks")` |
| `TestMessageHistory` | — | `agent.messages` returns a copy (not internal reference); assistant text persisted in history after turn |

**Key design verifications:**

- **The agent never imports hardware or UI code.** Verified by the grep check in the
  Definition of Done.
- **One tool, one tool call per response.** Tests 15–16 (tool schema included) and test 4
  (extra tool_use blocks dropped) enforce this structurally.
- **Pair-safe trimming.** Test 12 seeds history with a `tool_use`/`tool_result` pair and
  verifies the result is dropped (not orphaned) when the parent is trimmed.
- **Runaway protection at 20 calls/turn.** Test 13 queues 25 responses — loop stops at 20
  with a cap message.
- **Grant injection with Opus 4.8 / fallback.** Tests 9–10 verify the happy path; test 14
  simulates rejection and verifies the `<system-reminder>` fallback.

---

### `tests/integration/test_agent_live.py` — 1 test, ~120 lines

One live smoke test marked `@pytest.mark.llm`. **Skipped unless `ANTHROPIC_API_KEY` is set.**

| Test | What it covers |
|---|---|
| `test_live_get_device_info` | One benign round-trip against real Claude: "read device info and summarize." Asserts loop terminates, `get_device_info` was called, no `AgentError`. Does NOT assert on specific wording (non-deterministic). |

Enable with `pytest --llm` (a Part 8 concern; Part 6 just adds the marker).

---

## Test Design Principles

### Arrange → Act → Assert

Every test follows the three-phase pattern. A `make_command()` helper keeps construction
terse:

```python
def make_command(action: CommandAction, **args) -> ExecuteCommand:
    return ExecuteCommand(
        action=action,
        args=dict(args),
        justification="test",
        expected_effect="test",
    )
```

Tests read as: *given* this command and these grants, *when* we assess, *then* the level
is X and confirmation is Y.

### One behavior per test

Each test asserts one behavior. Edge cases get their own test functions with
descriptive names (`test_ism_wins_over_amateur_33cm`). This makes failures
self-documenting — the test name tells you exactly what broke.

### Parametrize for coverage, not exhaustiveness

`@pytest.mark.parametrize` is used to sweep boundary values (band edges, just-outside
frequencies) without exploding the test count. 19 `is_blocked` cases live in one
parametrized method.

### No I/O in unit tests

Unit tests import only from `hackrf_agent.domain.*`. No files, no network, no
hardware, no sqlite. No monkeypatching of system calls. Every test is a pure
function of its inputs.

---

## Quality Gates

All four must pass before a change is considered done:

```bash
# Tests — all safe-for-CI (no hardware, no LLM)
pytest tests/unit/ tests/integration/ -q -m "not hardware and not llm"

# Lint — target: clean
ruff check src/ tests/

# Types — target: clean
mypy src/

# No hardware/UI imports in ai/ package
grep -R "import pyhackrf\|from hackrf_agent.hw\|import numpy\|import rich\|import typer" src/hackrf_agent/ai/ ; echo "exit=$?"
# Expect: exit=1 (no matches)
```

Current status (2026-08-03):

| Gate | Status | Detail |
|---|---|---|
| `pytest tests/unit/ tests/integration/ -q -m "not hardware and not llm"` | 323 passed, 1 skipped | 65 new Part 6 tests (23 llm_client + 19 prompts + 23 agent loop) + 258 existing Parts 2–5 tests |
| `ruff check src/ tests/` | Clean | All Part 2–6 source and test files |
| `mypy src/` | Clean | `anthropic` handled via `# type: ignore[arg-type]` on SDK calls; `ignore_missing_imports` set globally |
| `grep` ai/ for hw/UI imports | Clean (exit=1) | Part 6 never touches hardware or UI |

---

## Adding New Tests

### Where to put them

- **Model validation** → `test_models.py`. Pydantic edge cases, default factories,
  enum exhaustiveness.
- **Frequency lookups** → `test_frequency_policy.py`. Band boundaries, inclusion
  checks, overlap detection.
- **Risk decisions** → `test_risk_assessor.py`. Decision tree branches, gain caps,
  grant interactions, action dispatch.
- **DSP primitives** → `test_dsp.py`. Synthetic IQ signals, peak recovery, noise
  floor estimation. Never needs hardware.
- **Subprocess safety** → `test_hackrf_subprocess.py`. Argv validation, allowlist
  enforcement, timeout/error paths. All processes mocked.
- **Driver validation** → `test_hackrf_driver.py`. Gain grid validation, sample
  rate validation, frequency bounds, lazy import guard, kill-switch ordering. No
  device opened.
- **DSP pipeline** → `test_dsp_pipeline.py`. End-to-end synthetic signal through
  quantization→FFT→peaks. The day-1 canary.
- **Hardware integration** → `test_hackrf_driver.py` (integration). Requires
  HackRF. RX-only. Marked `@pytest.mark.hardware`. Never TX.
- **LLM client** → `test_llm_client.py`. Protocol conformance, rate limiter logic,
  construction validation, test doubles. No real API calls.
- **Prompts & tool schema** → `test_prompts.py`. System prompt content, schema
  shape, enum values, determinism, byte-stability.
- **Agent loop** → `test_agent_loop.py` (integration). Full conversation loop with
  `FakeLLMClient` + real `CommandExecutor`/`FakeDriver`. Touches audit DB.
- **Live LLM** → `test_agent_live.py` (integration). One marker-gated round-trip
  against real Claude. Marked `@pytest.mark.llm`.

### Checklist for a new `CommandAction`

When a new action is added to the enum:

1. Add a decision branch in `RiskAssessor.assess()`.
2. Add a test class in `test_risk_assessor.py` covering:
   - Missing required args → BLOCKED
   - Valid args, lowest risk → expected tier
   - Valid args, higher risk → expected tier
   - Any blocked-band or hardware-limit edge cases
3. Run the full quality gates above.

---

## References

- **Test markers in `pyproject.toml`**: `hardware`, `llm`, `slow`
- **Pytest docs**: [docs.pytest.org](https://docs.pytest.org/)
- **Pydantic v2 validators**: [docs.pydantic.dev](https://docs.pydantic.dev/latest/concepts/validators/)
- **`docs/safety.md`** — Source of truth for every blocked band. Every entry in
  `BLOCKED_BANDS` must have a corresponding citation here.
- **`docs/development.md`** — Project layout, hardware setup, and code quality
  tooling.
