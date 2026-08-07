# `hackrf-agent-mcp` — MCP server for HackRF One

`hackrf-agent-mcp` exposes the same safety-gated HackRF command surface as
the chat CLI, but as a [Model Context Protocol][mcp] server. Any MCP-aware
host — Claude Desktop, Claude Code, Cursor, OpenCode, `mcp-cli`, custom
clients — can drive the radio through its tool, resource, and elicitation
surface.

[mcp]: https://modelcontextprotocol.io/

## Quick start

```bash
pip install "hackrf-agent[mcp,hackrf]"
```

The server starts on stdio:

```bash
hackrf-agent-mcp
# or equivalently:
hackrf-agent mcp
```

All logging goes to stderr. Stdout carries the MCP JSON wire protocol —
never write to stdout from inside a handler.

## Host configuration

We use Claude Code and OpenCode day-to-day. Both discover MCP servers from a
per-project `.mcp.json` in the repo root, so a single file wires up both
hosts at once. The repo already ships one — check it in and you're done:

```json
{
  "mcpServers": {
    "hackrf": {
      "command": "hackrf-agent-mcp",
      "args": []
    }
  }
}
```

Sanity-check the binary is on your `PATH` before either host tries to spawn
it:

```bash
which hackrf-agent-mcp
# → /usr/local/bin/hackrf-agent-mcp  (or a venv/pyenv path)
```

If it's not found, re-run `pip install "hackrf-agent[mcp,hackrf]"` in the
environment your host will inherit (`pyenv` shim, `uv tool install`, system
Python — whichever launches when the host spawns the subprocess).

### Claude Code

Claude Code auto-loads `./.mcp.json` when it starts in a directory that
contains one. On first use it prompts to approve the server; approve it
once per project.

- **Verify it loaded:** run `/mcp` inside Claude Code. `hackrf` should
  appear with status `connected` and the tool list from the table below.
- **Global fallback:** add the same `mcpServers` block to `~/.claude.json`
  if you want the server available outside this repo.
- **Debugging:** launch Claude Code with `--mcp-debug` to see the spawn
  command and stderr from `hackrf-agent-mcp`.

### OpenCode

OpenCode reads `.mcp.json` from the project root using the same schema.
No extra config is needed — open the repo in OpenCode and the `hackrf`
server appears in the MCP panel.

- **Verify it loaded:** open OpenCode's MCP panel (or run its equivalent
  of `/mcp`); `hackrf` should be listed with its tools.
- **Global fallback:** OpenCode also honors a user-level MCP config; add
  the same `mcpServers` block there if you want the server available in
  every project.
- **Elicitation:** OpenCode surfaces MCP elicitation prompts inline, so
  MEDIUM/HIGH approval flows work without extra setup.

### Manual testing (`mcp-cli`)

Useful when you want to poke tool calls without a full host:

```bash
mcp-cli --stdio -- hackrf-agent-mcp
```

## Tools

One MCP tool per `CommandAction`. Every tool requires two free-text fields:

| Field              | Purpose                                              |
|--------------------|------------------------------------------------------|
| `justification`    | Why the caller is invoking this action               |
| `expected_effect`  | What the caller expects to observe                   |

These are surfaced as required strings in every tool's JSON Schema so hosts
pass them through even when the operator is driving directly and the LLM is
not filling them in. They land in the audit log verbatim.

| MCP tool name             | Underlying action   | Risk (typical)   | RF activity |
|---------------------------|---------------------|------------------|-------------|
| `hackrf_get_device_info`  | `GET_DEVICE_INFO`   | LOW              | none        |
| `hackrf_sweep_spectrum`   | `SWEEP_SPECTRUM`    | LOW / MEDIUM     | RX only     |
| `hackrf_capture_iq`       | `CAPTURE_IQ`        | LOW / MEDIUM     | RX only     |
| `hackrf_transmit_iq`      | `TRANSMIT_IQ`       | MEDIUM / HIGH    | TX          |
| `hackrf_read_iq_summary`  | `READ_IQ_SUMMARY`   | LOW              | none        |
| `hackrf_decode_ook`       | `DECODE_OOK`        | LOW              | none        |
| `hackrf_grant_list`       | `GRANT_LIST`        | LOW              | none        |
| `hackrf_audit_query`      | `AUDIT_QUERY`       | LOW              | none        |

**Risk tiers:**

- **LOW** — auto-executes; no approval needed. Read-only admin actions,
  short RX sweeps (dwell ≤ 2 s), short captures (≤ 5 s).
- **MEDIUM** — host renders an approval prompt; operator clicks Allow or
  Deny. Long sweeps, long captures, ISM-band TX within grant limits.
- **HIGH** — same Allow/Deny prompt as MEDIUM; the tier is called out in
  the prompt text so the operator knows what they're approving.
  Amateur-band TX, unclassified-band TX, ISM TX above 30 dB gain. HIGH
  is never covered by `--auto-approve-medium`.
- **BLOCKED** — the server refuses the command before any hardware is
  touched. Protected bands (GPS, ADS-B, VHF guard, cellular), malformed
  arguments, out-of-range gain values.

### Per-tool argument reference

For the full argument reference, see
[docs/execute_command_schema.md](execute_command_schema.md). Every tool's
JSON Schema is derived from the same Pydantic models that validate
arguments in the chat CLI.

## Approval flow

MEDIUM and HIGH commands need a human decision. Under MCP the server pushes
an **elicitation request** back to the host; the host renders it to the
human; the human responds; the server resumes the command.

```
client (host)         hackrf-agent-mcp
     │  tools/call ───►
     │                    assess risk → MEDIUM/HIGH
     │  ◄─── elicitation/create (approval prompt)
     │  ── approve/deny ─►
     │                    execute or return error
     │  ◄─── tools/call result
```

- **MEDIUM** and **HIGH** commands: the elicitation carries no form
  fields. The host renders a plain confirmation prompt — click **Allow**
  to approve or **Deny** to deny. Same one-click flow at both tiers; the
  message text tells the operator which tier they're approving.
- **Timeout:** hosts typically time out elicitation prompts after 120 s.
  A timeout is treated as a denial.
- **Auto-approve MEDIUM:** pass `--auto-approve-medium` to the server (or
  set `auto_approve_medium = true` in `~/.hackrf-agent/config.toml`) to
  skip the MEDIUM prompt. HIGH is never auto-approved.
- **Hosts without elicitation:** the server checks host capabilities. If
  elicitation isn't supported, MEDIUM/HIGH tool calls fail with:
  *"approval channel not available; run `hackrf-agent grant tx …` or use a
  host that supports MCP elicitation."* LOW commands still work.

Pre-authorizing a band+gain via `hackrf-agent grant tx ...` reclassifies
matching transmissions as **LOW** (no per-command approval). This is the
recommended workflow for repeated TX in a known band.

## Resources

Resources mirror the read-only surface the chat CLI exposes through
`execute_command` (`grant_list`, `audit_query`). Hosts can browse and cache
them; tools remain available for ad-hoc queries.

| URI                                  | Backed by                              |
|--------------------------------------|----------------------------------------|
| `hackrf://audit/session/{id}`        | `AuditService.query(session_id=id)`    |
| `hackrf://audit/recent?limit=N`      | `AuditService.query(limit=N)`          |
| `hackrf://grants/active`             | `PermissionService.list_active()`      |
| `hackrf://grants/all`                | `PermissionService.list_all()`         |
| `hackrf://sessions/current`          | `SessionPaths` for this MCP session    |
| `hackrf://sessions/{id}/events`      | `AuditService.query(session_id=id)`, stable per-session URI so the assistant can subscribe rather than calling `audit_query` every turn. Optional `?limit=N` (default 200). |

IQ files are **not** exposed as resources. They can be GB-sized. The tool
that produces them returns the on-disk path, and hosts that want to load
them can use their own filesystem tools.

## Session model

One session per server process. The `session_id` is minted when
`hackrf-agent-mcp` starts and lives until the process exits. MCP hosts
typically spawn the server once per host session (Claude Desktop restart,
`mcp-cli` invocation), so IQ file paths remain stable for the whole
conversation.

The session ID is included in every tool response. IQ files are written
under `~/.hackrf-agent/sessions/<id>/iq/`.

## Concurrency

`HackrfDriver` wraps a single `libhackrf` handle and is not reentrant.
Concurrent tool calls are serialized behind an `asyncio.Lock`. The first-in /
first-out order matches the audit log's `COMMAND_RECEIVED` timestamps.

## Signal handling

- **First SIGINT** — aborts the current tool call, revokes active TX
  grants, returns an error tool result. The server stays alive.
- **Second SIGINT** within 2 s — exits the process.
- **SIGTERM** — revokes active TX grants, closes the driver, exits cleanly.

Hosts that spawn the server as a subprocess typically send `SIGTERM` on
shutdown.

## Safety

The MCP server uses the **same safety funnel** as the chat CLI. Every
command passes through:

1. `RiskAssessor` — deterministic tier assignment (LOW/MEDIUM/HIGH/BLOCKED)
2. `PermissionService` — grant checking (pre-authorized TX bands)
3. `McpApprovalPort` (via elicitation) — human decision for MEDIUM/HIGH
4. `HackrfDriver` — hardware dispatch (guarded by `asyncio.Lock`)

Every step is audited in `~/.hackrf-agent/agent.db`. See
[docs/safety.md](safety.md) for the full safety rationale.

**Key invariants:**

- No RF energy leaves the radio without a human decision (or a
  pre-authorized grant).
- The server never auto-approves HIGH commands regardless of flags.
- IQ paths are always under the session root; `..` traversal is rejected.
- All logging goes to stderr; the MCP wire on stdout is never corrupted.

## Limitations

- **Stdio transport only.** No HTTP / SSE in this release. The server can
  be wrapped in an HTTP transport later without touching the tool layer.
- **One radio per process.** `libhackrf` picks the first device. Multi-radio
  addressing (by serial) is deferred.
- **No LLM inside the server.** The MCP host is the LLM's home. The server
  never makes outbound API calls to OpenRouter or any other LLM provider.
- **macOS + Linux only.** The `hackrf` package installs via Homebrew or
  apt. Windows PRs welcome.
- **No sampling.** The MCP `sampling/create` request (server asks the host's
  LLM to complete something) is tempting for post-sweep summaries but
  re-imports the "LLM is a dependency" problem. Deferred.

## Logging

Set `HACKRF_MCP_LOG_LEVEL=DEBUG` for verbose logs (written to stderr):

```bash
HACKRF_MCP_LOG_LEVEL=DEBUG hackrf-agent-mcp
```

## Development

The MCP server lives under `src/hackrf_agent/mcp/`. Tests under
`tests/mcp/`. See [docs/development.md](development.md) for the
contribution guide.

To run MCP tests only:

```bash
pytest tests/mcp/ -v
```
