# Architecture

The definitive reference for how `hackrf-agent` fits together. Audience:
contributors who need to understand the whole system before making changes.

---

## Command-Reality Separation

The one-line principle, adapted from V3SP3R:

> You issue commands; the host enforces security. The model never touches the
> device or raw primitives. It only issues structured commands through the
> `execute_command` interface.

The LLM has no USB handle, no libhackrf, no shell. It only emits
`execute_command` JSON. Everything past that is Python's problem, and every
command funnels through the same deterministic chokepoint.

---

## Layer diagram

```
┌──────────────────────────────────────────────────────────┐
│  CLOUD (OpenRouter)                                    │
│  Sees: system prompt, chat history, ONE tool schema,     │
│         JSON tool results (never raw IQ)                 │
└─────────────▲───────────────────────────┬────────────────┘
              │                execute_command({
              │                  action, args,
              │                  justification,
              │                  expected_effect })
┌─────────────┴───────────────────────────▼────────────────┐
│  LAPTOP — Python process, run from a terminal            │
│  ("the reality enforcer" — no phone, no BLE, no Android) │
│  HackrfAgent  →  CommandExecutor  →  RiskAssessor        │
│                  ├─ PermissionService (scoped grants)    │
│                  ├─ FrequencyPolicy (allow/deny lists)   │
│                  ├─ Approval prompt (terminal / Textual) │
│                  ├─ ResultFormatter (bytes → summary)    │
│                  └─ AuditService (SQLite)                │
└─────────────────────────┬────────────────────────────────┘
                          │ libhackrf via pyhackrf
┌─────────────────────────▼────────────────────────────────┐
│  HackRF One (USB peripheral, no OS)                      │
└──────────────────────────────────────────────────────────┘
```

---

## Module map

| Package | Purpose |
|---------|---------|
| `hackrf_agent.ai` | LLM plumbing: `HackrfAgent` conversation loop, `LLMClient` protocol + OpenRouter impl, system prompt, `ResultFormatter` |
| `hackrf_agent.domain` | The chokepoint and its dependencies: `CommandExecutor`, `RiskAssessor`, `FrequencyPolicy`, `PermissionService`, `AuditService`, `ApprovalPort`, `SessionPaths`, `models.py` |
| `hackrf_agent.hw` | HackRF drivers: `HackrfDriver` (pyhackrf primary), `HackrfSubprocess` (escape hatch), `dsp.py` (FFT, peak detect, decoders) |
| `hackrf_agent.cli` | Human interface: Typer app, approval prompts, kill switch, grant commands, audit inspection |
| `hackrf_agent.data` | Persistence: `db.py` (connection factory, migrations), `schema.sql` (DDL) |

---

## Risk-tier table

Every `ExecuteCommand` is classified by the `RiskAssessor` into one of four tiers:

| Tier | Meaning | Examples |
|------|---------|----------|
| **LOW** | Read-only, no TX, bounded duration. Executed immediately. | `get_device_info`, `sweep_spectrum` (dwell ≤ 2 s), `capture_iq` (duration ≤ 5 s), `grant_list`, `audit_query`, `read_iq_summary`, `decode_ook` |
| **MEDIUM** | Longer capture, higher gain, disk writes, TX in known-safe hobby bands within an active grant. Requires operator approval (single `y` keypress). | `capture_iq` > 5 s, `sweep_spectrum` dwell > 2 s, `transmit_iq` in ISM band with gain ≤ 30 dB |
| **HIGH** | TX anywhere non-trivial, high gain, unclassified band, amateur band. Requires explicit operator confirmation (type `CONFIRM`). | `transmit_iq` with gain > 30 dB in ISM, TX in amateur bands, TX in unclassified frequencies |
| **BLOCKED** | Protected bands, illegal ranges. Refused by the host — the LLM cannot override. | ADS-B 1090 MHz, GPS L1/L2, aviation voice 118–137 MHz, maritime distress 156.8 MHz, cellular downlink |

The LLM never self-classifies risk. Tier assignment is a pure function of
`(action, args, active_grants)`.

---

## The envelope schema

Every action goes through `execute_command`:

```json
{
  "action": "<one of the CommandAction values>",
  "args": { "...": "..." },
  "justification": "Why this action is being taken.",
  "expected_effect": "What observable outcome is expected."
}
```

Per-action details are auto-generated in
[`docs/execute_command_schema.md`](execute_command_schema.md). The
machine-readable Draft-07 companion is at
[`schemas/execute_command.schema.json`](../schemas/execute_command.schema.json).

---

## Audit-log schema

Every command produces a `trace_id`-linked trail in SQLite:

```sql
CREATE TABLE audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trace_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  timestamp REAL NOT NULL,
  event TEXT NOT NULL,
  action TEXT,
  risk_level TEXT,
  payload_json TEXT,
  blocked_reason TEXT,
  duration_ms INTEGER
);
```

The six-event trail per command:
`COMMAND_RECEIVED → RISK_ASSESSED → [APPROVAL_REQUESTED → APPROVAL_GRANTED] → EXECUTED → RESULT`

BLOCKED commands produce a three-event trail:
`COMMAND_RECEIVED → RISK_ASSESSED → BLOCKED`

Denied approvals produce:
`COMMAND_RECEIVED → RISK_ASSESSED → APPROVAL_REQUESTED → APPROVAL_DENIED`

One `trace_id` UUID ties all events for a single `ExecuteCommand`. This is what
lets you replay a session offline and answer "why did my AI do that?"

---

## Data flow for one command

```
User message
    │
    ▼
HackrfAgent.chat()
    │  builds request (system prompt + history + tool schema)
    ▼
LLMClient.send()
    │  returns LLMResponse (text or tool_use)
    ▼
[if tool_use] ──► ExecuteCommand built from tool_use.input
    │
    ▼
CommandExecutor.execute(command)
    │
    ├─ 1. Mint trace_id; log COMMAND_RECEIVED
    ├─ 2. RiskAssessor.assess(command, active_grants); log RISK_ASSESSED
    ├─ 3. If BLOCKED → log BLOCKED; return refusal
    ├─ 4. If requires_confirmation → ApprovalPort.request(); log result
    ├─ 5. Dispatch to handler; log EXECUTED
    └─ 6. ResultFormatter.format(raw); log RESULT
    │
    ▼
Tool result returned to LLM as tool_result message
    │
    ▼
Loop continues or TurnEnded
```

---

## Failure modes and how they surface

| Failure | How it surfaces |
|---------|----------------|
| **BLOCKED band** | `RiskAssessor` returns `BLOCKED`; executor returns `CommandResult(success=False, message="Action blocked...")`. Handler never called. |
| **Approval denied** | `ApprovalPort.request()` returns `False`; executor returns `CommandResult(success=False, error="approval_denied")`. Handler never called. |
| **Hardware error** | Handler raises `HackrfError`; executor catches, returns `CommandResult(success=False, error="HackrfNotFoundError: ...")`. `RESULT` row logged with `success=False`. |
| **Argument error** | Handler raises `ValueError` (bad path, invalid arg); executor catches, returns `CommandResult(success=False, error="ValueError: ...")`. |
| **LLM refusal** | Provider returns `stop_reason="refusal"`; agent yields `TurnEnded(stop_reason="refusal")`. |
| **Runaway tool calls** | Agent loop caps at 20 tool calls per turn; yields `AgentError(recoverable=False, message="tool-call cap reached")`. |
