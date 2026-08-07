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

# Install pre-commit hooks
pre-commit install

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
testing is documented in `docs/safety.md`.

CI skips all `@pytest.mark.hardware` tests by default. The `--hardware` flag is
gated by a `pytest_addoption` hook in `tests/conftest.py`.

---

## Project Layout

```
hackrf-agent/
├── pyproject.toml                         # Build config, deps, tool settings
├── README.md                              # Entry point for new users
├── docs/
│   ├── architecture.md                    # Architecture reference
│   ├── safety.md                          # FCC citations, band policy, risk tiers
│   ├── development.md                     # This file
│   └── execute_command_schema.md          # Tool schema reference
├── schemas/
│   └── execute_command.schema.json        # Machine-readable JSON Schema
├── src/hackrf_agent/
│   ├── __init__.py
│   ├── ai/                                # LLM plumbing
│   │   ├── agent.py                       # HackrfAgent — conversation loop
│   │   ├── llm_client.py                  # LLMClient protocol + OpenRouterClient + FakeLLMClient
│   │   └── prompts.py                     # SYSTEM_PROMPT + EXECUTE_COMMAND_TOOL_SCHEMA
│   ├── domain/                            # Core logic (no I/O to hardware or LLM)
│   │   ├── models.py                      # Dataclasses & enums
│   │   ├── executor.py                    # CommandExecutor — the chokepoint
│   │   ├── risk_assessor.py               # LOW/MEDIUM/HIGH/BLOCKED
│   │   ├── frequency_policy.py            # BLOCKED_BANDS, ISM_BANDS
│   │   ├── permission_service.py          # Scoped, time-limited grants
│   │   ├── audit_service.py               # SQLite-backed audit log
│   │   ├── approval.py                    # ApprovalPort protocol + test doubles
│   │   ├── handlers.py                    # One async callable per CommandAction
│   │   ├── result_formatter.py            # bytes → compact JSON summaries
│   │   └── session.py                     # SessionPaths + new_session factory
│   ├── hw/                                # HackRF drivers
│   │   ├── hackrf_driver.py               # pyhackrf wrapper (primary)
│   │   ├── hackrf_subprocess.py           # CLI escape hatch
│   │   ├── dsp.py                         # FFT, peak detect, IQ conversion
│   │   └── exceptions.py                  # HackrfError hierarchy
│   ├── cli/                               # Terminal interface
│   │   ├── main.py                         # Typer app; mounts all subcommands
│   │   ├── parsing.py                      # Band, duration, gain parsers
│   │   ├── settings.py                     # SettingsService (config.toml + OPENROUTER_API_KEY env)
│   │   ├── kill_switch.py                  # SIGINT → stop_event + TX revoke
│   │   ├── approval.py                     # CliApprovalPort (MEDIUM Y/n, HIGH CONFIRM)
│   │   ├── permissions_cmd.py              # grant tx / list / revoke
│   │   ├── audit_cmd.py                    # audit tail
│   │   ├── doctor_cmd.py                   # doctor
│   │   ├── chat_cmd.py                     # chat REPL, event rendering
│   │   └── __init__.py
│   └── data/                              # Persistence
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
│   │   ├── test_session.py               # SessionPaths + new_session
│   │   ├── test_cli_parsing.py           # 23 tests — band/duration/gain parsers
│   │   ├── test_cli_settings.py          # SettingsService: config.toml + env-var api key
│   │   ├── test_cli_kill_switch.py       # 7 tests — SIGINT, double-Ctrl-C, revoke
│   │   └── test_cli_approval.py          # 7 tests — MEDIUM/HIGH prompts
│   ├── integration/                      # External deps (hardware, LLM, or fakes)
│   │   ├── test_agent_loop.py            # 23 tests — full agent loop with FakeLLMClient
│   │   ├── test_agent_live.py            # 1 @llm test — live Claude round-trip
│   │   ├── test_executor.py              # 17 tests — full executor funnel
│   │   ├── test_dsp_pipeline.py          # 2 tests — synthetic IQ through DSP
│   │   ├── test_hackrf_driver.py         # 3 @hardware tests — real device RX-only
│   │   ├── test_persistence_roundtrip.py # audit + grants round-trip
│   │   ├── test_cli_permissions.py       # 9 tests — grant tx/list/revoke CLI
│   │   ├── test_cli_audit.py             # 5 tests — audit tail CLI
│   │   ├── test_cli_doctor.py            # 5 tests — doctor diagnostics CLI
│   │   ├── test_cli_chat.py              # 1 @llm @hardware test — chat smoke
│   │   └── test_cli_main.py              # 4 tests — --help, no_args_is_help
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

# API key — read from the OPENROUTER_API_KEY environment variable ONLY.
# The user must export it in their shell before invoking the CLI (either
# directly, from their shell rc, or via `source ~/.openrouter_api_key`).
```

---

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `OPENROUTER_API_KEY` | API key for OpenRouter | For OpenRouter backend |
| `HACKRF_AGENT_CONFIG` | Override config file path (default: `~/.hackrf-agent/config.toml`) | No |
| `HACKRF_AGENT_LOG_LEVEL` | Python log level (default: `INFO`) | No |

---

## Testing

### Test Tiers

| Tier | Command | What runs |
|------|---------|-----------|
| **Unit** | `pytest tests/unit -q` | Pure logic — no hardware, network, or LLM. Default tier. |
| **Integration (safe)** | `pytest tests/integration -q -m "not hardware and not llm"` | Executor, agent loop, DSP pipeline, persistence roundtrip, CLI commands — all with fakes. Runs in CI on every push. |
| **End-to-end** | `pytest tests/e2e -q` | Full workflow tests with scripted LLM + fake driver + real audit DB. |
| **All safe-for-CI** | `pytest tests/unit/ tests/integration/ tests/e2e/ -q -m "not hardware and not llm"` | Everything that doesn't need hardware or a live API key. |
| **Hardware** | `pytest --hardware -m hardware -q` | Requires HackRF attached. RX-only. No TX. |
| **LLM** | `pytest --llm -m llm -q` | Requires `OPENROUTER_API_KEY`. Live round-trips against Claude via OpenRouter. |

### Pytest Markers

```bash
pytest --hardware                    # Enable hardware tests (HackRF required)
pytest --llm                         # Enable live LLM tests (OPENROUTER_API_KEY required)
pytest -m "not hardware and not llm" # Skip hardware and LLM tests (default)
```

The markers `hardware` and `llm` are orthogonal to the test tier (unit/integration/e2e).
Unit tests never carry either marker. The `tests/conftest.py` hook auto-skips
hardware/llm tests unless the corresponding flag is passed.

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

Three GitHub Actions workflows (in `.github/workflows/`):

- **`tests.yml`** — every push and PR. Runs lint, typecheck, unit tests (Python 3.11+3.12),
  and integration+e2e tests (no markers). Fast; no secrets needed.
- **`tests-llm.yml`** — nightly cron at 03:00 UTC + manual dispatch. Runs
  `@pytest.mark.llm` tests with the org's `OPENROUTER_API_KEY` secret.
- **`tests-hardware.yml`** — manual dispatch only. Runs on a self-hosted runner
  with the `hackrf-attached` label. Runs `@pytest.mark.hardware` tests with
  real HackRF attached. Never scheduled — TX could physically transmit if a test
  slips through the safety gate.

### Self-Hosted Hardware Runner

Set up one Mac mini or Linux box with a HackRF plugged in and the GitHub Actions
runner registered with the `hackrf-attached` label. The runner needs `hackrf` CLI
tools installed and udev rules configured. See the Hardware Setup section above.

---

## Code Quality

```bash
# Lint (target: clean)
ruff check src/ tests/

# Format (target: clean)
ruff format --check src/ tests/

# Type check (target: clean)
mypy src/hackrf_agent/

# Run pre-commit on all files
pre-commit run --all-files
```

Pre-commit hooks (configured in `.pre-commit-config.yaml`):
- `ruff check --fix` + `ruff format`
- `mypy` on `src/`
- Schema regeneration: runs `scripts/generate_execute_command_schema.py` when
  `models.py`, `prompts.py`, or the regenerator itself changes.
- Schema no-drift: on push, verifies the regenerated files match committed versions.

---

## Adding a New CommandAction

Every RF, knowledge, or analysis capability lands as a new
`CommandAction` value — never as a second MCP tool that bypasses the
funnel. This checklist is authoritative; a PR that skips items 1–14
is not landing.

### The 14-item reviewer's checklist

1. **New `CommandAction` value** in `src/hackrf_agent/domain/models.py`.
   Group with related actions (knowledge tier, analysis tier, action
   tier) and match the existing comment structure.
2. **New args model** in `src/hackrf_agent/domain/args.py`. Pydantic
   v2, `frozen=True`, `extra="forbid"`. Register in `ARGS_BY_ACTION`
   and add to the `ActionArgs` discriminated union.
3. **`RiskAssessor` classifies it deterministically** in
   `src/hackrf_agent/domain/risk_assessor.py`. Knowledge and analysis
   verbs are hardcoded `LOW` (add to the read-only branches).
   TX-adjacent verbs go through the existing tier table. **The gate
   never reads editable config** — coupling the risk tier to editable
   `records/*.json` is forbidden; the gate stays hardcoded in Python.
4. **New handler function** in
   `src/hackrf_agent/domain/handlers.py`, dispatched from `HANDLERS`.
   Handlers return JSON-primitive dicts with a `kind` marker.
5. **Executor formatter pass-through** in
   `src/hackrf_agent/domain/executor.py:_format`. Knowledge and
   analysis handlers already have a shared branch that returns raw +
   strips the `kind` marker + sets `risk_tier=LOW`. Add your new
   `kind` string to that branch (or add a dedicated `format_*` method
   in `result_formatter.py` for hardware-side actions).
6. **New MCP tool description entry** in
   `src/hackrf_agent/mcp/tool_registry.py:_TOOL_DESCRIPTIONS`.
7. **New prompt entry** in `src/hackrf_agent/ai/prompts.py`. Add
   under the appropriate tier heading (Knowledge / Analysis / Act).
   Bump `SYSTEM_PROMPT_VERSION` if the prompt content changes.
8. **Schema regenerator entry** in
   `scripts/generate_execute_command_schema.py:PER_ACTION_DOCS`. Run
   the script; commit the resulting `docs/execute_command_schema.md`
   and `schemas/execute_command.schema.json` changes.
9. **Unit test for the args model** — validation, defaults, rejection
   of out-of-range values. Add to `tests/unit/test_handlers.py` or a
   new file if the verb has substantial DSP.
10. **Handler test** in `tests/unit/test_handlers.py`. Exercise the
    happy path + the reject-outside-session-root path if the handler
    reads files.
11. **MCP registry test** in `tests/mcp/test_tool_registry.py`. At
    minimum a dispatch round-trip; more if the args model has
    validation rules.
12. **Integration test in `tests/integration/`** if the handler
    crosses a subsystem boundary (touches the audit log, the
    permission service, or the driver).
13. **`CHANGELOG.md` entry** under the current "Unreleased" section.
14. **No new import of `pyhackrf` or `hw.hackrf_driver` outside `hw/`
    and `domain/executor.py` dispatch.** Automated grep in CI. The
    knowledge and analysis tiers must not import hardware modules.

### Corpus-side additions

If the new action reads files from `knowledge/`:

- Add a fixture in `tests/fixtures/knowledge/` (or synthesize one in
  the test).
- Include an explicit test that path traversal is rejected (any input
  matching `../` or containing `..` must raise `KnowledgeError` or
  `ValueError`).

### If the new action is a decoder

- Round-trip test — synthesize a known signal in the test, run the
  decoder, assert the recovered payload matches. See
  `tests/unit/test_analysis.py::TestDecodeAdsB::test_round_trips_synthetic_frame`
  as a model.
- Update `records/protocols.json` with a matching record. Include the
  MCP verb name in `tools_downstream`.

### Final gates

```bash
python scripts/generate_execute_command_schema.py  # regenerate docs
pytest tests/unit/ tests/mcp/ -q                    # 596+ tests must pass
pre-commit run --all-files                          # linters + schema drift
```

---

## References

- **`docs/ai-package.md`** — LLM integration architecture, agent loop, prompts, tool schema
- **`docs/cli.md`** — CLI reference, all commands, approval flow, kill switch, config
- **`docs/tests.md`** — Complete test documentation, all tiers, all files, quality gates
- **`docs/safety.md`** — FCC citations, band policy, risk tiers
- **HackRF Wiki**: [github.com/greatscottgadgets/hackrf/wiki](https://github.com/greatscottgadgets/hackrf/wiki)
- **pyhackrf on PyPI**: [pypi.org/project/pyhackrf/](https://pypi.org/project/pyhackrf/)
- **OpenRouter API Docs**: [openrouter.ai/docs](https://openrouter.ai/docs)
- **V3SP3R Architecture**: [github.com/elder-plinius/V3SP3R](https://github.com/elder-plinius/V3SP3R) (included in this repo as `M0MA-V3SP3R/`)
- **SQLite WAL Mode**: [sqlite.org/wal.html](https://sqlite.org/wal.html)
