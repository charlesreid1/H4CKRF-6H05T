# CLI Reference

The `hackrf-agent` command-line interface — the human interface that assembles
Parts 2–6 into a shipping product.

---

## Quick Start

```bash
# Export your OpenRouter API key (or `source` a dotfile that does)
export OPENROUTER_API_KEY=sk-or-v1-...

# First-run diagnostic
hackrf-agent doctor

# Grant a TX window
hackrf-agent grant tx 433.05-434.79M --for 30m

# Start interactive chat
hackrf-agent chat
```

---

## Command Reference

### `chat` — Interactive REPL

```
hackrf-agent chat [--auto-approve-medium]
```

Starts an interactive chat session with the HackRF agent. The REPL consumes
`HackrfAgent.chat(...)` events and renders them with `rich`:

- `[agent]` — Assistant text from Claude
- `→ tool <action>` — Tool call started (dim, with justification)
- `← ok / ← fail` — Tool call completed (green/red)
- `(model refused)` — The model declined the request
- `! error` — Unrecoverable error

**In-REPL commands:** `/quit`, `/exit` — exit the REPL. Everything else is
sent to the agent as a message.

**Kill switch:** Ctrl-C once during an in-flight command (sweep, capture, TX)
aborts the operation, revokes all TX grants, and returns to the REPL prompt.
Ctrl-C twice within 2 seconds performs a hard exit. Ctrl-C during idle exits
immediately.

**Options:**
- `--auto-approve-medium` — Skip the Y/n prompt for MEDIUM-risk commands.
  HIGH-risk commands still require typing `CONFIRM`.

**Requirements:**
- `OPENROUTER_API_KEY` exported in the shell environment
- HackRF One connected via USB (or `FakeDriver` for dry-run testing)

---

### `doctor` — First-Run Diagnostic

```
hackrf-agent doctor
```

Runs six checks and prints a checklist with three-state status:

| Status | Colour | Meaning |
|--------|--------|---------|
| `OK` | green | Required or optional feature is working |
| `WARN` | yellow | Optional tool unavailable — exit code still 0 |
| `FAIL` | red | Required feature broken — exit code 1 |

| Check | What it verifies | Required? |
|---|---|---|
| `home_dir` | `~/.hackrf-agent/` exists and is writable | Yes |
| `db_schema` | SQLite schema is up to date (`ensure_schema` idempotent) | Yes |
| `api_key` | `OPENROUTER_API_KEY` env var is set in the shell environment | Yes |
| `hackrf` | HackRF One enumerates via `hackrf_info` subprocess | Yes |
| `rtl_433` | `rtl_433` is on PATH (needed for `analyze_pulses`) | No — WARN on absent |
| `urh_cli` | `urh_cli` is on PATH (needed for `demodulate_bits`) | No — WARN on absent |

Exit code 0 if all required checks pass, 1 if any `FAIL`. A `WARN` never
contributes to the exit code. The `hackrf` check uses `hackrf_info`
subprocess — `pyhackrf` is not required.

---

### `grant` — TX Permission Management

```
hackrf-agent grant tx <band> --for <duration> [--max-gain <dB>]
hackrf-agent grant list
hackrf-agent grant revoke <uuid>
```

#### `grant tx`

Issues a scoped, time-limited TX grant. The grant permits transmission in the
specified frequency band at or below the specified gain, for the specified
duration.

**Band format:**
```
"315M"              → ISM 315 MHz band (310–320 MHz)
"433.05-434.79M"    → Explicit range (MHz)
"902M-928M"         → Two-sided explicit units
"2400000000-2483500000" → Raw Hz range
```

**Duration format:** `"90s"`, `"30m"`, `"2h"` (seconds, minutes, hours)

**Options:**
- `--max-gain <dB>` — Maximum TX VGA gain (0–47 dB, default 20)

**Example:**
```bash
hackrf-agent grant tx 433.05-434.79M --for 30m --max-gain 20
# Granted TX 433050000–434790000 Hz (max_gain=20 dB) until 2026-08-03T14:30:00-07:00
# id: a1b2c3d4-...
```

#### `grant list`

Lists all active (non-expired, non-revoked) TX grants in a table:
```
                 Active TX grants
┌──────────────────┬─────────────────┬─────────────┬──────────────────────┐
│ id               │ band (Hz)       │ max_gain_db │ expires (local)      │
├──────────────────┼─────────────────┼─────────────┼──────────────────────┤
│ a1b2c3d4...      │ 433050000–4347… │          20 │ 2026-08-03T14:30:00  │
└──────────────────┴─────────────────┴─────────────┴──────────────────────┘
```

#### `grant revoke`

Revokes a specific grant by UUID. The grant is marked as revoked and will
no longer satisfy future TX authorization checks.

---

### `audit` — Audit Log Query

```
hackrf-agent audit tail [--session <id>] [--trace <uuid>] [--limit <n>]
```

Pretty-prints recent audit rows in table form. Each row shows:
- Local timestamp
- Event type (`COMMAND_RECEIVED`, `EXECUTED`, `APPROVAL_GRANTED`, etc.)
- Command action
- Risk level
- Duration (ms)
- Trace UUID (first 8 chars)

**Options:**
- `--session <id>` — Filter by session ID
- `--trace <uuid>` — Filter by trace UUID
- `--limit <n>` — Max rows to display (default 50)

**Example:**
```bash
hackrf-agent audit tail --limit 10
```

---

## Global Options

### `--home-dir`

```
hackrf-agent --home-dir <path> [command]
```

Overrides the default `~/.hackrf-agent` directory. All state (database,
config, sessions, captures) is stored under this path. Useful for testing
and for running multiple isolated instances.

```bash
# Production (default)
hackrf-agent grant list

# Testing with isolated state
hackrf-agent --home-dir /tmp/test-agent grant list
```

---

## Configuration

### `config.toml`

Located at `~/.hackrf-agent/config.toml`. Non-secret settings:

```toml
model = "anthropic/claude-sonnet-5"
max_history_messages = 24
auto_approve_medium = false
```

| Key | Type | Default | Description |
|---|---|---|---|
| `model` | string | `"anthropic/claude-sonnet-5"` | OpenRouter model ID |
| `max_history_messages` | integer | 24 | Max messages in conversation history |
| `auto_approve_medium` | boolean | false | Skip Y/n prompt for MEDIUM-risk commands |

The file is written atomically (`.tmp` → rename) and read with full defaults
on missing or malformed content. Unknown keys are ignored.

### API Key Storage

The OpenRouter API key is read from the `OPENROUTER_API_KEY` environment
variable — full stop. `SettingsService` does not read any file. The user is
responsible for exporting the variable in their shell before invoking the CLI
(directly, from their shell rc, or by `source`-ing a git-ignored dotfile like
`~/.openrouter_api_key`).

For CI or shared machines, use the platform's secrets manager to inject the
variable into the process environment.

---

## Approval Flow

The terminal approval prompt (`CliApprovalPort`) is the concrete
implementation of the `ApprovalPort` protocol. It is called by the executor
for every command with `risk.requires_confirmation == True`.

### MEDIUM Risk

```
┌─ Pending command ───────────────────────────┐
│ Action:        transmit_iq                  │
│ Risk:          MEDIUM                       │
│ Reason:        TX in ISM 433 band, ≤30 dB   │
│ Justification:  Testing OOK modulation      │
│ Expected effect: Signal visible on nearby   │
│                  spectrum analyzer          │
│   args.center_freq_hz: 433920000            │
│   args.sample_rate_hz: 2000000              │
└─────────────────────────────────────────────┘
Approve? [y/N]:
```

User types `y` or `n`. If `auto_approve_medium` is enabled in config,
the prompt is skipped and the command is auto-approved.

### HIGH Risk

```
┌─ Pending command ───────────────────────────┐
│ Action:        transmit_iq                  │
│ Risk:          HIGH                         │
│ Reason:        TX gain 45 dB exceeds grant  │
│                cap of 30 dB                 │
│ ...                                         │
└─────────────────────────────────────────────┘
Type CONFIRM to approve (anything else denies):
```

User must type the literal string `CONFIRM`. Anything else (including
`confirm`, `y`, `yes`) denies the command. This is a typo-resistant guard
for high-risk operations.

### LOW Risk

LOW-risk commands (`get_device_info`, `grant_list`, `audit_query`, etc.)
bypass approval entirely.

### BLOCKED Commands

BLOCKED commands are refused by the executor before the approval port is
reached. They appear in the audit log with `event=BLOCKED`.

---

## Kill Switch

| Action | Behavior |
|---|---|
| Ctrl-C (once) | Set shared `stop_event`, revoke all TX grants, abort in-flight operation |
| Ctrl-C (twice, < 2 s apart) | Hard exit — `loop.stop()` |
| Ctrl-C during idle | Immediate exit (no in-flight operation to abort) |
| Ctrl-C during non-chat command | Plain `KeyboardInterrupt` (kill switch not installed) |

The kill switch is active only during `hackrf-agent chat`. Non-chat commands
(`grant`, `audit`, `doctor`) use Python's default SIGINT → `KeyboardInterrupt`
behavior.

### Design Rationale

- **One keystroke.** The operator must never guess how to stop transmitting.
- **Graceful first, fatal second.** A single Ctrl-C aborts the current operation
  cleanly (driver raises `KillSwitchTriggered`, agent turn ends, REPL returns).
  A second Ctrl-C within 2 seconds stops the event loop and exits the process
  for panic situations.
- **TX grants revoked on first Ctrl-C.** Even if the operator walks away mid-sweep,
  the next Ctrl-C revokes all TX authorizations. Any subsequent TX attempt
  requires re-granting.

---

## File Layout

```
~/.hackrf-agent/
├── config.toml              # Non-secret settings
├── agent.db                 # SQLite database (audit log + grants)
└── sessions/
    └── <session-id>/        # One directory per chat session
        ├── capture-0001.iq  # Raw IQ captures
        ├── sweep-0001.json  # Spectrum sweep results
        └── payloads/        # Generated IQ files for TX
```

---

## Architecture

```
hackrf-agent (main.py Typer app)
├── --home-dir  → SettingsService in ctx.obj
├── chat        → _run_chat
│                   ├── ensure_schema
│                   ├── new_session → session_id, SessionPaths
│                   ├── KillSwitch.install_handler(loop)
│                   ├── async with AuditService, HackrfDriver:
│                   │     CliApprovalPort ← console
│                   │     CommandExecutor ← everything above
│                   │     OpenRouterClient ← model, api_key
│                   │     HackrfAgent    ← llm, executor
│                   │     _repl:
│                   │        while True:
│                   │          user_text = Prompt.ask (on thread)
│                   │          stop_event.clear()
│                   │          async for ev in agent.chat(user_text):
│                   │             render ev with rich
│                   └── KillSwitch.uninstall_handler(loop)
│
├── grant tx <band> --for <dur>     → PermissionService.grant
├── grant list                      → PermissionService.list_active
├── grant revoke <uuid>             → PermissionService.revoke
├── audit tail [--session] [--trace] → AuditService.query
└── doctor                          → check home_dir, db, api_key, hackrf_info,
                                        rtl_433, urh_cli (three-state: OK/WARN/FAIL)
```

---

## References

- **`docs/development.md`** — Project layout, hardware setup, quality tooling
- **`docs/safety.md`** — BLOCKED bands, risk tiers, FCC citations
- **`docs/tests.md`** — Test documentation including Part 7 CLI tests
- **`docs/ai-package.md`** — LLM integration architecture (Part 6)
