# Troubleshooting

Symptom → fix, sorted by where it bites you. Skim the section headings;
you're probably here mid-CTF and don't have time to read prose.

If a fix here says "run `hackrf-agent doctor`", start there — it's a
2-second check that catches five of the top ten failure modes.

---

## Install & first launch

### `hackrf_info` prints nothing / hangs

The OS doesn't see the radio. `hackrf-agent doctor` will fail at the
`hackrf` check.

1. Re-seat the USB cable. Data-capable USB-A → USB-mini. Charge-only
   cables enumerate as nothing.
2. Skip hubs and USB-C dongles for the first bring-up.
3. **macOS:** `system_profiler SPUSBDataType | grep -A 8 HackRF` — if
   the OS sees it here but `hackrf_info` doesn't, the Homebrew install
   is broken. Reinstall: `brew reinstall hackrf`.
4. **Ubuntu:** `lsusb | grep 1d50` — if the OS sees it but you get a
   permission error, the udev rules didn't land. Re-run the udev step
   from the Quick Start in `Readme.md`, then unplug/replug.

### `hackrf_info` says "Resource busy" / `HackrfBusyError`

Something else has the device open. Common culprits:

- Another `hackrf-agent` process. `ps aux | grep hackrf-agent`.
- `gqrx`, `SDR#`, `URH`, `CubicSDR`, `SDR++`.
- A stale `hackrf_transfer` from a killed shell.

Close them or `kill` the PID. If the busy state persists after
closing everything, unplug/replug the radio — libhackrf occasionally
leaves the handle claimed after a hard crash.

### `hackrf-agent doctor` — `pyhackrf: import failed`

The Python wrapper isn't installed in the active environment.

```bash
pip install 'hackrf-agent[hackrf]'
```

If you have multiple Python installs (pyenv, `uv`, system), make sure
the shell that runs `hackrf-agent` is using the venv you installed
into: `which hackrf-agent` and `which python` should point at the
same prefix.

### `pip install -e '.[dev]'` — "Failed building wheel for pyhackrf"

`pyhackrf` links against the system `libhackrf`. The library must be
installed *first*.

- **macOS:** `brew install hackrf` (installs `libhackrf` + CLI +
  headers).
- **Ubuntu:** `sudo apt install hackrf libhackrf-dev libhackrf0`.

Then re-run the pip install.

### Firmware mismatch — decoder silently misbehaves

Old firmware sometimes returns short or misaligned buffers. Check with:

```bash
hackrf-agent doctor --strict
```

The `firmware` check line shows the version string. Compare against
the latest release at
[github.com/greatscottgadgets/hackrf/releases](https://github.com/greatscottgadgets/hackrf/releases).
To upgrade, see the flashing instructions in `Readme.md` step 2.

---

## API keys & the chat CLI

### `hackrf-agent chat` — "OPENROUTER_API_KEY not set"

The chat CLI reads the key from the shell environment — nothing else.
There is no `.env` auto-load.

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Or `source ~/.openrouter_api_key` from a git-ignored dotfile. See
[env_reference.md](env_reference.md) for the exact rules on how
leading/trailing whitespace is stripped.

The MCP server (`hackrf-agent-mcp`) does **not** need this key — it's
purely for the built-in chat REPL.

### OpenRouter returns 401

The key is set but rejected.

- Copy-paste error — leading `Bearer `, trailing newline, wrong prefix.
  The key should start with `sk-or-v1-`.
- Key was revoked or hit its credit cap. Log into OpenRouter and check
  the dashboard.
- Wrong header — if you're driving the API directly (not via
  `OpenRouterClient`), the header is `Authorization: Bearer <key>`.

### Model refuses to use tools / never calls `execute_command`

The default model is set in `src/hackrf_agent/ai/llm_client.py`
(`DEFAULT_MODEL`). Some smaller / older OpenRouter models don't
tool-call reliably. Switch to a stronger tool-user:

```toml
# ~/.hackrf-agent/config.toml
model = "anthropic/claude-sonnet-5"
```

Restart `hackrf-agent chat`.

---

## MCP server won't attach

### `hackrf-agent-mcp` command not found

The MCP install extra didn't run.

```bash
pip install 'hackrf-agent[mcp,hackrf]'
which hackrf-agent-mcp
```

The `which` result must be on the `PATH` your MCP host will inherit.
If you're launching Claude Code from a GUI and installed into a
`pyenv` shim, the GUI shell may not see the shim. Options:

1. Install into a Python that's on the system `PATH` (Homebrew Python
   on macOS, distro Python on Ubuntu).
2. In `.mcp.json`, use the absolute path:
   ```json
   { "mcpServers": { "hackrf": {
     "command": "/Users/you/.venvs/hackrf/bin/hackrf-agent-mcp",
     "args": []
   } } }
   ```

### `/mcp` inside Claude Code shows the server as failed

Launch Claude Code with `--mcp-debug` to see the spawn command and the
server's stderr. Common causes:

- Server crashes on import → `pyhackrf` missing in the target env.
  Install `hackrf-agent[hackrf]`.
- Wrong Python version → the server requires Python ≥ 3.11.
- `libhackrf` not installed → the server tolerates a missing HackRF
  at startup (knowledge tools still work) but crashes if the
  `pyhackrf` C library can't find `libhackrf`.

### The MCP tools list is empty in the host

The server booted but the host isn't rendering tools. Run the manual
test path to confirm the server is healthy:

```bash
mcp-cli --stdio -- hackrf-agent-mcp
```

If `mcp-cli` shows the tools but Claude Code / OpenCode doesn't,
restart the host — MCP tool discovery is cached per-session.

### No approval prompt appears for MEDIUM/HIGH commands

The host doesn't support MCP elicitation.

- The server checks `capabilities.elicitation` on connect and refuses
  MEDIUM/HIGH tool calls with a clear error: *"approval channel not
  available; run `hackrf-agent grant tx …` or use a host that
  supports MCP elicitation."*
- LOW commands still work.
- Fix: pre-authorize the TX with `hackrf-agent grant tx <band>
  --for <dur>` in a terminal, then retry. In-grant TX reclassifies to
  LOW and skips the elicitation.

---

## Runtime — sweeps, captures, transmits

### `sweep_spectrum` returns `truncated: true`

The requested span exceeds `sample_rate_hz`. The driver can only see
one bandwidth of `sample_rate_hz` around the tuner center; the extra
range on the ends is silently dropped.

Fix: raise `sample_rate_hz` (up to 20 Msps), narrow the span, or use
`sweep_spectrum_bulk` with explicit sub-ranges each ≤ `sample_rate_hz`.

### `capture_iq` output is huge / fills the disk

IQ files are `cs8`, interleaved I/Q — **2 bytes per sample**. Size:

```
bytes = sample_rate_hz × duration_s × 2
```

At the default 2 Msps, 1 s = 4 MB. At 8 Msps, 1 s = 16 MB. A 60-s
capture at 8 Msps is ~960 MB. See [iq_handling.md](iq_handling.md)
for the arithmetic and cleanup tips.

Cap the session with `MAX_CAPTURE_MINUTES` in the environment to
force early refusal before hardware is touched:

```bash
export MAX_CAPTURE_MINUTES=10
```

### `capture_iq` — signal shows a fake DC spike on top of the target

You used `center_freq_hz` and set it equal to the frequency of
interest. The HackRF LO leaks a DC bias that always lands at the
tuner center.

Fix: pass `target_freq_hz` instead of `center_freq_hz`. The executor
offsets the tuner by `sample_rate_hz / 4` so the DC spike lands in a
different FFT bin from your signal. See `analyze_iq_carrier_frequency`
if you're stuck with an already-captured file.

### `transmit_iq` — "no grant covers this frequency"

Every TX needs either:
1. A pre-authorized grant that covers band + gain + time-window, OR
2. An interactive MEDIUM/HIGH approval via the CLI prompt or MCP
   elicitation.

If the elicitation path isn't available (headless host, `--auto-approve-medium`
scope, etc.), issue a grant first:

```bash
hackrf-agent grant tx 433.05-434.79M --for 30m --max-gain 20
```

### `transmit_iq` on a protected band — refused

Working as intended. See [safety.md](safety.md) for the BLOCKED band
table. GPS, ADS-B, aviation voice, cellular downlink, marine distress
etc. are refused before the driver is invoked, regardless of grants.
This is not a bug and there is no override.

### `KillSwitchTriggered` mid-capture

You hit Ctrl-C once. The current operation was aborted, all TX
grants were revoked. The REPL / MCP server is still running; issue
a fresh grant and retry if you want to continue.

A second Ctrl-C within 2 s hard-exits the process.

### "Cumulative capture would exceed MAX_CAPTURE_MINUTES"

Session-level belt-and-suspenders (see [safety.md — Session Budgets](safety.md#session-budgets-max_capture_minutes-max_tx_seconds)).
The cap is enforced before the driver is invoked, so no RF activity
occurred.

Options:
- Raise or clear `MAX_CAPTURE_MINUTES` in the environment and
  **restart the process** — the budget is read at executor
  construction time, not per-command.
- Restart the CLI to zero the counter (per-session, not global).

Same logic applies to `MAX_TX_SECONDS`.

---

## Knowledge corpus & lore

### `KnowledgeError: cannot locate knowledge/ corpus`

The server can't find the corpus on disk.

- If you're running an installed wheel, the package doesn't ship the
  corpus as `package_data` — you must run from a checkout that
  contains `knowledge/MANIFEST.md`.
- If you're running from a checkout but the module is imported from
  a different path (site-packages), set the env var:
  ```bash
  export HACKRF_KNOWLEDGE_DIR=/path/to/H4CKRF-6H05T/knowledge
  ```

### `knowledge_search` returns nothing for a term you know is there

Search is case-insensitive substring across markdown only. It does
not cross into `records/*.json`. For structured lookups, prefer:

- `knowledge_lookup_band` for a frequency
- `knowledge_lookup_modulation` for a family name
- `knowledge_lookup_protocol` for a named protocol
- `knowledge_lookup_decoder` for a line code
- `knowledge_lookup_keyfob` for a vendor/model

Free-text `knowledge_search` is a last resort.

---

## Audit & grants

### `grant list` shows expired grants

`grant list` shows *active* grants (non-expired, non-revoked) by
default. If you see stale entries after their TTL, restart the
process — the CLI caches the list per invocation.

### Grant issued but TX still asks for approval

The grant doesn't match. Check:

- **Band** — the grant's frequency range must contain `center_freq_hz`
  in its entirety at the requested bandwidth. `433.05-434.79M` does
  **not** cover `434.900M`.
- **Gain** — `tx_vga_gain_db` must be ≤ the grant's `--max-gain`.
- **Expiry** — grants have hard TTLs. `hackrf-agent grant list` shows
  the expiry time in local time.
- **Ctrl-C** — a single Ctrl-C in the current session revokes all
  active TX grants. Re-issue.

### The audit log is enormous

`hackrf-agent doctor --strict` warns at 100k rows, hard-fails at 1M.
Rotate:

```bash
hackrf-agent audit rotate
```

(Rotate moves the current `agent.db` aside; queries still work on
the new empty DB.)

---

## Debugging

### Turn on MCP debug logs

```bash
HACKRF_MCP_LOG_LEVEL=DEBUG hackrf-agent-mcp
```

Logs go to **stderr**. Never write to stdout inside the MCP process —
that stream carries the JSON wire protocol.

### Reconstruct a specific command from the audit log

Every `execute_command` gets a `trace_id`. Pull the full event chain:

```bash
hackrf-agent audit tail --trace <uuid>
```

You'll see `COMMAND_RECEIVED` → risk assessment → approval decision →
execution outcome. If a command was refused, the row explains why.

### Reset all state (last resort)

```bash
# Danger: wipes captures, audit log, config, grants.
rm -rf ~/.hackrf-agent/
```

Then re-run `hackrf-agent doctor`.

---

## When to file a bug

- The gate approved a BLOCKED band (should never happen).
- The gate refused something you believe should pass — include the
  `hackrf-agent audit tail --trace <uuid>` dump.
- The MCP server crashes with a traceback that doesn't start in
  `hackrf_agent.*`.

Include: OS, Python version, `hackrf_info` output, `hackrf-agent
doctor --strict` output. Redact your API key if it somehow appears
(the audit log doesn't store credentials).

---

## Cross-references

- [Readme.md](../Readme.md) — first-time install
- [safety.md](safety.md) — BLOCKED bands, risk tiers, session budgets
- [mcp.md](mcp.md) — MCP host setup, elicitation flow
- [cli.md](cli.md) — full CLI reference
- [env_reference.md](env_reference.md) — every env var + config key
