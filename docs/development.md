# Development Guide

How to set up, run, and contribute to `hackrf-agent`.

---

## Quick Start

```bash
# Requirements: Python ≥ 3.11, libhackrf (for HackRF hardware access)

git clone https://github.com/charlesreid/hackrf-agent.git
cd hackrf-agent

# Set up Python 3.11+ (pyenv shown; venv or conda also fine)
pyenv local 3.11.14
python -m venv .venv
source .venv/bin/activate

# Install in dev mode with all extras
pip install -e ".[dev]"

# Verify the install
hackrf-agent doctor
```

---

## Hardware Setup

### macOS

1. Install libhackrf via Homebrew:
   ```bash
   brew install hackrf
   ```

2. Verify device enumeration:
   ```bash
   hackrf_info
   ```
   Expected output: serial number, firmware version, board revision, part ID.

3. USB permissions: HackRF uses a vendor-class (WCID) USB interface. On macOS,
   no special entitlement or kernel extension is needed — libhackrf accesses the
   device via IOKit userspace USB (IOUSBHost). If the device doesn't enumerate:
   - Check the USB cable (data-capable, not charge-only).
   - Try a different USB port (avoid hubs for initial testing).
   - Run `system_profiler SPUSBDataType | grep -A 10 HackRF` to confirm the OS sees it.

4. **Note on pyhackrf + libhackrf**: pyhackrf is a C extension that wraps libhackrf.
   `libhackrf` must be installed at the system level before pyhackrf will function.
   Without it, `import pyhackrf` will fail with missing symbols.

### Linux

1. Install libhackrf via package manager or from source:
   ```bash
   # Debian/Ubuntu
   sudo apt install hackrf libhackrf-dev

   # Or from source: https://github.com/greatscottgadgets/hackrf
   ```

2. Install udev rules (from the HackRF wiki):
   ```bash
   sudo cp /usr/share/hackrf/53-hackrf.rules /etc/udev/rules.d/
   # Or create /etc/udev/rules.d/53-hackrf.rules with:
   # ATTR{idVendor}=="1d50", ATTR{idProduct}=="6089", MODE="0666"
   # ATTR{idVendor}=="1d50", ATTR{idProduct}=="604b", MODE="0666"
   # ATTR{idVendor}=="1d50", ATTR{idProduct}=="cc15", MODE="0666"
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

3. Verify: `hackrf_info`

### No Hardware?

The core logic (models, policy, risk, permissions, audit, LLM loops, CLI) can be
developed and tested without HackRF hardware. Tests marked `@pytest.mark.hardware`
are skipped by default. See [Testing](#testing) below.

### Running Hardware Tests (Manual)

When a HackRF One is attached, run the hardware-marked tests with:

```bash
pytest tests/integration/test_hackrf_driver.py --hardware -v
```

Three tests run:

1. **`test_get_device_info`** — opens the device, reads serial/firmware/board
   revision, asserts non-empty strings.
2. **`test_sweep_spectrum_returns_expected_shape`** — 100 ms RX sweep of the
   433–434 MHz ISM band at 2 Msps; asserts correct array shapes and dtypes.
3. **`test_kill_switch_aborts_sweep`** — starts a 5 s sweep in a background task,
   fires `stop_event.set()` after 100 ms, asserts `KillSwitchTriggered` within 2 s.

**Never TX in automated tests.** No `transmit_iq` test exists; manual TX smoke
testing is covered by the Part 8 runbook.

CI skips all `@pytest.mark.hardware` tests by default. The `--hardware` flag is
gated by a `pytest_addoption` hook (to be added in `tests/conftest.py` when CI
infrastructure is set up).

**Current status (2026-08-03):** HackRF One is not connected to this development
machine. `hackrf_info` verification is deferred. The `pyhackrf` package imports as
`import hackrf` but will fail at `CDLL('libhackrf.so.0')` until libhackrf is installed
via Homebrew (`brew install hackrf`).

---

## Project Layout

```
hackrf-agent/
├── pyproject.toml                         # Build config, deps, tool settings
├── README.md                              # Entry point for new users
├── docs/
│   ├── architecture.md                    # Architecture reference (Part 8)
│   ├── safety.md                          # FCC citations, band policy, risk tiers
│   ├── development.md                     # This file
│   └── execute_command_schema.md          # Tool schema reference (Part 7)
├── schemas/
│   └── execute_command.schema.json        # Machine-readable JSON Schema
├── src/hackrf_agent/
│   ├── __init__.py
│   ├── ai/                                # LLM plumbing (Part 6 — COMPLETE)
│   │   ├── agent.py                       # HackrfAgent — conversation loop
│   │   ├── llm_client.py                  # LLMClient protocol + AnthropicClient + FakeLLMClient
│   │   └── prompts.py                     # SYSTEM_PROMPT + EXECUTE_COMMAND_TOOL_SCHEMA
│   ├── domain/                            # Core logic (no I/O to hardware or LLM)
│   │   ├── models.py                      # Dataclasses & enums
│   │   ├── executor.py                    # CommandExecutor — the chokepoint
│   │   ├── risk_assessor.py               # LOW/MEDIUM/HIGH/BLOCKED
│   │   ├── frequency_policy.py            # BLOCKED_BANDS, ISM_BANDS
│   │   ├── permission_service.py          # Scoped, time-limited grants
│   │   ├── audit_service.py               # SQLite-backed audit log
│   │   ├── approval.py                    # ApprovalPort protocol + test doubles (prod impl in Part 7)
│   │   ├── handlers.py                    # One async callable per CommandAction
│   │   ├── result_formatter.py            # bytes → compact JSON summaries
│   │   └── session.py                     # SessionPaths + new_session factory
│   ├── hw/                                # HackRF drivers (Part 4 — COMPLETE)
│   │   ├── hackrf_driver.py               # pyhackrf wrapper (primary)
│   │   ├── hackrf_subprocess.py           # CLI escape hatch
│   │   ├── dsp.py                         # FFT, peak detect, IQ conversion
│   │   └── exceptions.py                  # HackrfError hierarchy
│   ├── cli/                               # Terminal interface (Part 7 — PLANNED)
│   │   └── __init__.py
│   └── data/                              # Persistence (Part 3 — COMPLETE)
│       ├── db.py                           # ensure_schema + open_connection
│       └── schema.sql                     # DDL for audit + grants
├── tests/
│   ├── unit/                              # No hardware, no network, no LLM
│   │   ├── test_llm_client.py            # 23 tests — LLM client fakes, rate limiter, construction
│   │   ├── test_prompts.py               # 19 tests — system prompt, tool schema, determinism
│   │   ├── test_models.py                # 17 tests — domain model validation
│   │   ├── test_risk_assessor.py         # 41 tests — risk decision tree
│   │   ├── test_frequency_policy.py      # 37 tests — band tables, blocked/ISM checks
│   │   ├── test_dsp.py                   # 23 tests — FFT, peak detection, IQ conversion
│   │   ├── test_hackrf_subprocess.py     # 14 tests — argv validation, allowlist, error paths
│   │   ├── test_hackrf_driver.py         # 33 tests — gain/freq/sample rate validation
│   │   ├── test_db.py                    # schema + connection tests
│   │   ├── test_audit_service.py         # audit log writer + reader
│   │   ├── test_permission_service.py    # grant CRUD + TTL enforcement
│   │   ├── test_approval.py              # ApprovalPort protocol + test doubles
│   │   ├── test_handlers.py              # handler dispatch + arg extraction
│   │   ├── test_result_formatter.py      # format helpers for each action
│   │   └── test_session.py               # SessionPaths + new_session
│   ├── integration/                      # External deps (hardware, LLM, or fakes)
│   │   ├── test_agent_loop.py            # 23 tests — full agent loop with FakeLLMClient
│   │   ├── test_agent_live.py            # 1 @llm test — live Claude round-trip
│   │   ├── test_executor.py              # 17 tests — full executor funnel
│   │   ├── test_dsp_pipeline.py          # 2 tests — synthetic IQ through DSP
│   │   ├── test_hackrf_driver.py         # 3 @hardware tests — real device RX-only
│   │   └── test_persistence_roundtrip.py # audit + grants round-trip
│   ├── e2e/                              # Full workflow with fake LLM + mock HW
│   └── fixtures/
│       ├── iq/                            # Golden .iq files
│       └── audit/                         # Canonical audit DB snapshots
└── .venv/                                 # Virtual environment (gitignored)
```

---

## Session-Scratch Directory Layout

All runtime artifacts land under `~/.hackrf-agent/`:

```
~/.hackrf-agent/
├── config.toml              # Non-secret settings (model, defaults, UI prefs)
├── agent.db                 # SQLite database (audit log + grants)
└── sessions/
    └── <session-id>/        # One directory per chat session
        ├── capture-0001.iq  # Raw IQ captures
        ├── capture-0002.iq
        ├── sweep-0001.json  # Spectrum sweep results
        └── payloads/        # Generated IQ files for TX
```

The `session_id` is a UUID minted by the CLI when `hackrf-agent chat` starts.
Session directories are created lazily on first capture/TX.

**Rule:** The LLM never names arbitrary paths. All output lands under the session
directory; all path arguments the LLM passes are validated against this constraint
by the executor (see `ProtectedPaths` pattern in V3SP3R).

Data directories on macOS:
```
# Config, DB, sessions
~/.hackrf-agent/

# Logs
~/Library/Logs/hackrf-agent/

# API key (macOS Keychain)
# Stored via `keyring` library; service name: "hackrf-agent"
```

---

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `ANTHROPIC_API_KEY` | API key for Claude (Anthropic) | For Anthropic backend |
| `OPENROUTER_API_KEY` | API key for OpenRouter | For OpenRouter backend |
| `OLLAMA_HOST` | Ollama server URL (default: `http://localhost:11434`) | For Ollama backend |
| `HACKRF_AGENT_CONFIG` | Override config file path (default: `~/.hackrf-agent/config.toml`) | No |
| `HACKRF_AGENT_LOG_LEVEL` | Python log level (default: `INFO`) | No |

---

## Testing

### Test Tiers

| Tier | Command | What runs |
|------|---------|-----------|
| **Unit** | `pytest tests/unit -q` | Pure logic — no hardware, network, or LLM. Default tier. **240+ tests across 14 files.** |
| **Integration (safe)** | `pytest tests/integration -q -m "not hardware and not llm"` | Executor, agent loop, DSP pipeline, persistence roundtrip — all with fakes. Runs in CI on every push. **80+ tests.** |
| **Integration (hardware)** | `pytest tests/integration --hardware -q` | Requires HackRF attached. RX-only tests. No TX. 3 tests in `test_hackrf_driver.py`. |
| **Integration (LLM)** | `pytest tests/integration --llm -q` | Requires `ANTHROPIC_API_KEY`. One benign round-trip. |
| **End-to-end** | `pytest tests/e2e -q` | Full workflow with fake LLM + mock hardware. |
| **All safe-for-CI** | `pytest tests/unit/ tests/integration/ -q -m "not hardware and not llm"` | All unit + integration-safe. **323 tests, completes in ~20 s.** |

### Pytest Markers

```
pytest --hardware       # Enable hardware tests (HackRF required)
pytest --llm            # Enable live LLM tests (ANTHROPIC_API_KEY required)
pytest -m "not slow"    # Skip slow tests
```

### Writing Tests

- **Unit tests**: Colocated with their module in `tests/unit/`. No fixtures needed
  beyond what pytest provides. Drive `frequency_policy.is_blocked(freq_hz)` with
  boundary values. Drive `risk_assessor.assess()` with every `(CommandAction, band,
  grant_state)` combination.
- **Integration tests**: Mock external dependencies with fakes (e.g., `FakeApprovalPort`,
  `FakeLLMClient`). Use `sqlite3.connect(":memory:")` for persistence tests.
- **Hardware tests**: Decorate with `@pytest.mark.hardware`. Always use a bounded
  sweep or short capture. **Never TX in automated tests.**
- **LLM tests**: Decorate with `@pytest.mark.llm`. Use cheap, short prompts.
  Assert structural properties of the response, not specific content.

### CI

GitHub Actions matrix (defined in `.github/workflows/ci.yml`, to be created):

- `unit`: `pytest tests/unit -q` — every push
- `integration`: `pytest tests/integration -q -m "not hardware and not llm"` — every push
- `hardware`: `pytest --hardware` — self-hosted runner only, nightly
- `llm`: `pytest --llm` — nightly cron with secrets

---

## Code Quality

```bash
# Lint (target: clean)
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check (target: clean)
mypy src/

# Verify ai/ package never imports hardware or UI
grep -R "import pyhackrf\|from hackrf_agent.hw\|import numpy\|import rich\|import typer" src/hackrf_agent/ai/
# Expect: exit=1 (no matches)
```

Pre-commit hooks (to be configured in `.pre-commit-config.yaml`):
- `ruff check` + `ruff format`
- `mypy` on `src/`
- Schema regeneration (`execute_command.schema.json` from Pydantic model)
- No committed `.iq` files over 1 MB
- `grep` check — ai/ package must not import hardware or UI

---

## Adding a New CommandAction

Checklist (see `docs/execute_command_schema.md` for the full reference):

1. Add the enum value to `CommandAction` in `models.py`.
2. Add the Pydantic args model (or extend the existing args schema).
3. Add a row to the risk table in `risk_assessor.py` — every new action needs a
   defined tier for every band it could touch.
4. Add a test case in `tests/unit/test_risk_assessor.py`.
5. Add the action handler in `handlers.py` (dispatch table).
6. Add a result-formatting rule in `result_formatter.py`.
7. Add handler wiring in `executor.py` (the dispatcher dict in `HANDLERS`).
8. Regenerate `schemas/execute_command.schema.json` and `docs/execute_command_schema.md`.
9. Add the action to `SYSTEM_PROMPT` in `prompts.py` so the LLM knows about it.
10. Add an agent-loop test in `tests/integration/test_agent_loop.py` exercising the
    new action through the LLM tool-use path.

---

## References

- **`docs/ai-package.md`** — LLM integration architecture (Part 6), agent loop, prompts, tool schema
- **`docs/tests.md`** — Complete test documentation, all tiers, all files, quality gates
- **`docs/safety.md`** — FCC citations, band policy, risk tiers
- **HackRF Wiki**: [github.com/greatscottgadgets/hackrf/wiki](https://github.com/greatscottgadgets/hackrf/wiki)
- **pyhackrf on PyPI**: [pypi.org/project/pyhackrf/](https://pypi.org/project/pyhackrf/)
- **Anthropic Tool Use Docs**: [docs.anthropic.com/en/docs/build-with-claude/tool-use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- **V3SP3R Architecture**: [github.com/elder-plinius/V3SP3R](https://github.com/elder-plinius/V3SP3R) (included in this repo as `M0MA-V3SP3R/`)
- **SQLite WAL Mode**: [sqlite.org/wal.html](https://sqlite.org/wal.html)
