# Environment Reference

Every configuration knob H4CKRF exposes, in one table.

Three surfaces feed into runtime behavior:

1. **Environment variables** — read at process start.
2. **`~/.hackrf-agent/config.toml`** — read on demand by the CLI and
   MCP server.
3. **CLI flags** — passed on the command line, override both above
   where they overlap.

If a knob isn't listed here, it isn't a knob.

---

## Environment variables

| Variable | Default | Consumer | Purpose |
|---|---|---|---|
| `OPENROUTER_API_KEY` | *(unset)* | `hackrf-agent chat` | OpenRouter API key used by the built-in chat REPL. Not required for `hackrf-agent-mcp`. See [cli.md § API Key Storage](cli.md#api-key-storage). |
| `MAX_CAPTURE_MINUTES` | *(unset — disabled)* | `CommandExecutor` | Session-cumulative cap on `capture_iq` `duration_s`. Positive float (minutes). Empty/unset/non-numeric/≤0 → disabled. Read once at executor construction. See [safety.md § Session Budgets](safety.md#session-budgets-max_capture_minutes-max_tx_seconds). |
| `MAX_TX_SECONDS` | *(unset — disabled)* | `CommandExecutor` | Session-cumulative cap on `transmit_iq` on-air time. Positive float (seconds). Empty/unset/non-numeric/≤0 → disabled. Read once at executor construction. |
| `HACKRF_MCP_LOG_LEVEL` | `INFO` | `hackrf-agent-mcp` | Python logging level (any of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). Case-insensitive. Logs go to stderr — never stdout, which carries the MCP wire. |
| `HACKRF_KNOWLEDGE_DIR` | *(auto-discovered)* | Knowledge tier | Override for the `knowledge/` corpus location. Normally the corpus is auto-discovered by walking up from the module looking for `knowledge/MANIFEST.md`. Set this when running an installed wheel without a checkout, or in tests. |

### Value parsing quirks

- `MAX_CAPTURE_MINUTES` and `MAX_TX_SECONDS` are parsed with
  `float()`. A malformed value silently disables the budget — the
  process does not error out. If in doubt, check the executor log
  at DEBUG level.
- `OPENROUTER_API_KEY` is stripped of leading/trailing whitespace.
  Empty after stripping → treated as unset.
- Budgets are read **once**, at executor construction time. Changing
  them mid-session (e.g. re-exporting inside the chat REPL) has no
  effect. Restart the process.

---

## `~/.hackrf-agent/config.toml`

Non-secret settings. Read by `SettingsService` on demand. Written
atomically (`.tmp` → rename). Unknown keys are ignored.

```toml
model = "anthropic/claude-sonnet-5"
max_history_messages = 24
auto_approve_medium = false
```

| Key | Type | Default | Consumer | Purpose |
|---|---|---|---|---|
| `model` | string | `DEFAULT_MODEL` (see `src/hackrf_agent/ai/llm_client.py`) | `hackrf-agent chat` | OpenRouter model ID for the chat CLI. Common values: `anthropic/claude-sonnet-5`, `anthropic/claude-opus-4-8`, `deepseek/deepseek-v4-pro`. |
| `max_history_messages` | integer | `24` | `hackrf-agent chat` | Max messages retained in the LLM conversation history. History is trimmed pair-safely (keeps assistant/tool response pairs together). |
| `auto_approve_medium` | boolean | `false` | `hackrf-agent chat`, `hackrf-agent-mcp` | Skip the MEDIUM-risk approval prompt (`y/N` in the CLI, elicitation in MCP). HIGH is **never** auto-approved regardless of this setting. |

### Notes

- The file is optional. On a fresh install it doesn't exist; defaults
  apply.
- On a malformed TOML file, the CLI logs a warning (via Python
  `logging`) and returns defaults — it does not crash.
- No secret goes in this file. `OPENROUTER_API_KEY` is env-only by
  design.
- `hackrf-agent-mcp` reads `auto_approve_medium` from this file only
  — there is no CLI flag for the MCP server.

---

## CLI flags

Global (all subcommands, defined in
`src/hackrf_agent/cli/main.py`):

| Flag | Default | Purpose |
|---|---|---|
| `--home-dir <path>` | `~/.hackrf-agent` | Override the state directory. All state (database, config, sessions, captures) lives under this path. Useful for isolated testing and running multiple instances. |

Per-subcommand:

### `hackrf-agent chat`

| Flag | Default | Purpose |
|---|---|---|
| `--auto-approve-medium` | off | Skip the `y/N` prompt for MEDIUM-risk commands. HIGH still requires typing `CONFIRM`. Overrides `auto_approve_medium=false` in `config.toml`; equivalent when the config value is `true`. |

### `hackrf-agent doctor`

| Flag | Default | Purpose |
|---|---|---|
| `--strict` | off | Also validate: `pyhackrf` importable, `hackrf_info` firmware string, corpus discoverable, `records/*.json` valid, audit DB row count under 1M. Soft warnings become hard failures under `--strict`. Use before an event. |

### `hackrf-agent grant tx`

| Flag / arg | Default | Purpose |
|---|---|---|
| `<band>` (positional) | required | Frequency range. Formats: `"315M"`, `"433.05-434.79M"`, `"902M-928M"`, `"2400000000-2483500000"`. |
| `--for <duration>` | required | Grant duration. Formats: `"90s"`, `"30m"`, `"2h"`. |
| `--max-gain <dB>` | `20` | Maximum TX VGA gain, 0–47 dB. Requests with `tx_vga_gain_db` above this fall through to normal MEDIUM/HIGH approval. |

### `hackrf-agent grant revoke`

| Flag / arg | Default | Purpose |
|---|---|---|
| `<uuid>` (positional) | required | Grant ID from `hackrf-agent grant list`. |

### `hackrf-agent audit tail`

| Flag | Default | Purpose |
|---|---|---|
| `--session <id>` | *(all)* | Filter by session ID. |
| `--trace <uuid>` | *(all)* | Filter by trace UUID (one command's full event chain). |
| `--limit <n>` | `50` | Max rows to display. |

### `hackrf-agent audit rotate`

| Flag | Default | Purpose |
|---|---|---|
| `--keep-days <n>` | `30` | Rows older than this are deleted. |
| `--vacuum / --no-vacuum` | `--vacuum` | Run SQLite `VACUUM` after the delete to reclaim disk space. |

### `hackrf-agent lore`

| Subcommand | Flag | Default | Purpose |
|---|---|---|---|
| `search` | `--max-results <n>` | `10` | Max hits from `knowledge_search`. |
| `lookup-keyfob` | `--vendor <str>` | *(any)* | Vendor substring filter. |
| `lookup-keyfob` | `--model <str>` | *(any)* | Model substring filter. |

`lore read`, `lore lookup-band`, `lore lookup-modulation`, and
`lore lookup-protocol` take positional arguments only. See
[cli.md § `lore`](cli.md#lore--search-the-rfsigint-knowledge-corpus).

### `hackrf-agent mcp` / `hackrf-agent-mcp`

The MCP server takes **no CLI flags**. It reads `home_dir` and
`auto_approve_medium` from `SettingsService` (i.e. the default
`~/.hackrf-agent/` and `config.toml`). To point the server at a
different home dir, set the home dir via `hackrf-agent --home-dir
<path> mcp` (the global flag applies).

---

## Precedence

Where multiple surfaces set the same knob, the effective value is:

1. **CLI flag** (highest priority) — e.g. `--auto-approve-medium`
   forces auto-approve on for that invocation regardless of
   `config.toml`.
2. **`config.toml`** — persistent per-user setting.
3. **Environment variable** — for the specific vars listed above;
   most `config.toml` keys have no env counterpart.
4. **Compiled default** (lowest priority) — as coded in the source.

Budget env vars (`MAX_CAPTURE_MINUTES`, `MAX_TX_SECONDS`) have no
CLI or `config.toml` counterpart — env var or nothing.

---

## What is *not* configurable

Deliberate omissions — these are baked into the source and by
design not user-tunable:

- **BLOCKED bands.** The list is hardcoded in
  `src/hackrf_agent/domain/frequency_policy.py`. Editing the file
  weakens the gate; that's a code change, not a config change. See
  [safety.md](safety.md).
- **Risk-tier thresholds.** The 5-s capture cap, 2-s sweep-dwell
  cap, 30-dB MEDIUM-gain cap, and 47-dB hardware cap are all
  constants in `risk_assessor.py`.
- **Gate order.** RiskAssessor → PermissionService → ApprovalPort →
  Driver. Not configurable.
- **`IQ` file format.** Always `.cs8` — see [iq_handling.md](iq_handling.md).
- **HIGH-risk auto-approval.** No flag, env var, or config key can
  turn this on. Typing `CONFIRM` is the only path.

---

## Cross-references

- [cli.md](cli.md) — full CLI reference with usage examples
- [mcp.md](mcp.md) — MCP server config file and host setup
- [safety.md](safety.md) — session budgets, grant model
- [troubleshooting.md](troubleshooting.md) — when a setting isn't
  taking effect
