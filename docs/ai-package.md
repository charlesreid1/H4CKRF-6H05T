# AI Package — LLM Integration Architecture

How `src/hackrf_agent/ai/` connects the model (cloud) to the executor (host-side
deterministic policy). This is Part 6 of the `hackrf-agent` build plan.

---

## Overview

The `ai` package is the **LLM front-end**. It invents no new domain concepts and
never talks to hardware directly. Its only output side is `CommandExecutor.execute()`.

Three files, three responsibilities:

```
src/hackrf_agent/ai/
├── llm_client.py   # LLMClient protocol + OpenRouterClient + FakeLLMClient
├── prompts.py      # SYSTEM_PROMPT + EXECUTE_COMMAND_TOOL_SCHEMA (pure data)
└── agent.py        # HackrfAgent.chat() — the conversation loop
```

---

## Data Flow

```
user_message (str)
     │
     ▼
HackrfAgent.chat(user_message)
     │
     ├── trim history (pair-safe, last 24 messages)
     ├── fetch active grants from PermissionService
     ├── build per-turn system message (grant injection)
     ├── LLMClient.send(system, messages, tools=[execute_command])
     │
     ├── stop_reason == "end_turn" ──► TurnEnded, return
     ├── stop_reason == "refusal" ───► TurnEnded, return
     │
     └── stop_reason == "tool_use":
           │
           ├── extract first tool_use block (drop extras with warning)
           │
           ├── name != "execute_command"
           │      └─► AgentError(recoverable=True), continue loop
           │
           ├── invalid input
           │      └─► AgentError(recoverable=True), continue loop
           │
           └── valid:
                 │
                 ├── ToolCallStarted(action, args, justification, expected_effect)
                 ├── CommandExecutor.execute(command)  ─► CommandResult
                 ├── ToolCallCompleted(action, result)
                 ├── append tool_result to messages
                 └── loop (bounded by 20 calls/turn)
```

Every branch produces at most one `TurnEnded` OR an unrecoverable `AgentError`. The
audit log (Part 3, driven by Part 5's executor) captures every `execute_command` call
with a `trace_id`. The LLM sees only compact JSON summaries — never raw IQ, never
`bytes`, never `ndarray`.

---

## `llm_client.py` — Client Abstraction

### `LLMClient` (Protocol)

The agent loop depends on this protocol, not on any concrete implementation. This
is how tests inject `FakeLLMClient` and how future backends (OpenRouter, Ollama)
plug in.

```python
class LLMClient(Protocol):
    async def send(
        self,
        *,
        system: list[dict[str, Any]] | str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> LLMResponse: ...
```

### `OpenRouterClient`

Concrete implementation backed by the `openai` SDK pointed at OpenRouter. Key behaviors:

- **Lazy import:** `openai` is imported inside `__init__`, so `FakeLLMClient`
  and response helpers are importable without the SDK installed.
- **API key resolution:** Constructor arg → `OPENROUTER_API_KEY` env var. Never
  reads from disk or keyring — that's Part 7's job.
- **Rate limiter:** At most 30 requests per rolling 60-second window. Enforced
  via `collections.deque[float]` of timestamps + `asyncio.Lock`. On saturation,
  `send()` awaits until a slot opens; it does NOT raise.
- **Model:** `anthropic/claude-sonnet-5` by default. Override via
  `OpenRouterClient(model=...)`.
  The agent loop never hard-codes a model string — it's injected via the
  `LLMClient` protocol.
- **Retries:** SDK default (`max_retries=2`) handles 429/5xx. No second retry
  loop is layered on top.
- **Non-streaming:** Tool-use loops are simpler non-streaming. UI streaming is
  a Part 7 concern if desired.

#### Rate Limiter Design

```python
async def _wait_for_slot(self) -> None:
    async with self._lock:
        while True:
            now = time.monotonic()
            # Drop timestamps older than the window.
            while self._timestamps and now - self._timestamps[0] > 60.0:
                self._timestamps.popleft()
            if len(self._timestamps) < 30:
                self._timestamps.append(now)
                return
            # Sleep until the oldest slot ages out.
            wait_s = 60.0 - (now - self._timestamps[0]) + 0.01
            await asyncio.sleep(wait_s)
```

The sleep is inside the lock because the agent loop is single-consumer. If
fan-out (multiple concurrent callers sharing one client) is added later, rewrite
with `asyncio.Condition` and move the sleep outside the critical section.

### `FakeLLMClient`

Test double with a deterministic queue of canned `LLMResponse` objects:

- `responses` — list of pre-built responses; each `send()` pops from the head.
- `calls` — list of dict snapshots of every `send()` invocation. Tests assert
  on what the agent sent to the LLM.
- Raises `IndexError` if the queue is empty (fail loud, don't hang).

### Response-Building Helpers

Two functions for building canned responses without touching the SDK:

- `make_text_response(text, stop_reason="end_turn")` — text-only response.
- `make_tool_use_response(tool_name, tool_input, tool_use_id, preamble)` —
  tool_use response with optional preamble text.

Both use `_FakeContentBlock` — a duck-typed dataclass matching the SDK's
`.type` / `.text` / `.name` / `.input` / `.id` shape.

---

## `prompts.py` — Prompt & Tool Schema

Pure data. Zero I/O. No imports beyond `domain.models`.

### `SYSTEM_PROMPT`

A ~2.5K character (est. 1.6K tokens) system prompt with these sections:

1. **Operator's mission** — "You are the AI brain of a HackRF One SDR agent..."
2. **Frequency band reference** — ISM 315, ISM 433, 902–928, 2.4 GHz tables
   plus BLOCKED bands (ADS-B 1090, GPS L1/L2, aviation voice, maritime distress,
   cellular, emergency services).
3. **Risk tiers** — LOW / MEDIUM / HIGH / BLOCKED with one-line trigger
   descriptions.
4. **Command envelope** — Inline JSON example of a `sweep_spectrum` on ISM 433,
   plus a reference table of all 8 actions and their required args.
5. **Operating discipline** — 8 rules covering sweep-before-capture, the risk
   gate, one-tool-call-per-response, justification requirements, blocked band
   refusal, grant expiry, and compact summaries.

The prompt is **byte-stable across turns** for prompt caching. No session id,
current date, or per-run value is interpolated. All volatile data goes into
per-turn `messages`.

`SYSTEM_PROMPT_VERSION` is a `YYYY-MM-DD-vN` string — bump it on any content
change.

### `EXECUTE_COMMAND_TOOL_SCHEMA`

Built at import time from Pydantic's `ExecuteCommand.model_json_schema()`:

```python
{
    "function": {
        "name": "execute_command",
        "description": "Request that the host execute exactly one HackRF action...",
        "parameters": { ... }  # Pydantic-generated JSON Schema, titles stripped
    }
```

Key properties:
- **Generated once at import time** — deterministic across sessions and
  `importlib.reload`.
- **Pydantic `title` fields stripped** — noisy and unhelpful for the model.
- **`$defs` preserved** — Pydantic v2 uses `$ref` for enum types; the
  `CommandAction` enum values live under `$defs/CommandAction/enum`.
- **Enum values are string values** — `"get_device_info"`, not `"GET_DEVICE_INFO"`
  — because `CommandAction(str, Enum)` emits values by default.

---

## `agent.py` — Conversation Loop

### Event Stream

`HackrfAgent.chat()` is an async generator that yields typed, frozen dataclasses.
The caller (Part 7's CLI) pattern-matches on `.type`:

| Event | `.type` | Carries |
|---|---|---|
| `AssistantText` | `"assistant_text"` | `.text` — a text block from the model |
| `ToolCallStarted` | `"tool_call_started"` | `.action`, `.args`, `.justification`, `.expected_effect` |
| `ToolCallCompleted` | `"tool_call_completed"` | `.action`, `.result` (the `CommandResult`) |
| `TurnEnded` | `"turn_ended"` | `.stop_reason` — `"end_turn"` or `"refusal"` |
| `AgentError` | `"agent_error"` | `.message`, `.recoverable` — whether the loop continues |

A simple turn produces: `AssistantText` → `TurnEnded`.
A tool-use turn produces: `AssistantText` (optional) → `ToolCallStarted` →
`ToolCallCompleted` → (repeat up to 20×) → `TurnEnded`.

### Message History

The agent owns a `list[dict[str, Any]]` of provider-format messages. Key
behaviors:

- **Pair-safe trimming:** Before each request, the history is trimmed to the
  last `MAX_HISTORY_MESSAGES` (24) entries. If trimming would land in the middle
  of an assistant `tool_use` / user `tool_result` pair, the entire pair is
  dropped. This prevents orphaned `tool_result` messages that would cause a
  400 error on the next request.
- **Grant injection:** Active TX grants are injected as a per-turn
  `{"role": "system", "content": "..."}` message appended to `messages[]`. This
  is NOT persisted to `self._messages` — it's rebuilt from the live grant list
  on every request. This avoids caching stale grant state.
- **Mid-conversation system fallback:** Claude Opus 4.8 is the only model that
  accepts mid-conversation `system` messages. If the configured model rejects
  it (400 mentioning `role 'system' is not supported`), the agent falls back to
  injecting a `<system-reminder>...</system-reminder>` text block into the most
  recent user message. This fallback happens once per session; subsequent turns
  skip the attempt entirely.

### Tool Call Dispatch

When the model returns `stop_reason == "tool_use"`:

1. Extract the first `tool_use` block. If there are more than
   `MAX_TOOL_CALLS_PER_RESPONSE` (1), log a warning and drop extras.
2. If the tool name is not `"execute_command"` — return a `tool_result(is_error=True)`
   with a descriptive message. The model gets to try again. This is a recoverable
   error.
3. Build an `ExecuteCommand` from the tool input via Pydantic constructor.
   Missing required fields, bad enum values, or type mismatches → recoverable
   error.
4. Yield `ToolCallStarted`, then `await executor.execute(command)`, then
   `ToolCallCompleted(result=...)`.
5. Append the `tool_result` message to history. If `result.success` is False,
   set `is_error=True` so the model sees the failure clearly.
6. Loop (bounded by `max_tool_calls_per_turn = 20`).

### Message Format Translation

The ``OpenRouterClient`` translates between the internal message format
(Anthropic-shaped, for minimal agent-loop churn) and the OpenAI Chat
Completions wire format that OpenRouter exposes. See ``llm_client.py`` for
the field-by-field mapping.

### Error Handling Philosophy

| Scenario | Behavior |
|---|---|
| `end_turn` | Normal termination. Persist assistant turn, yield `TurnEnded`. |
| `refusal` | Model declined for safety reasons. Yield `TurnEnded(refusal)`. Do NOT retry the same prompt. |
| `max_tokens`, `pause_turn`, unknown | Yield `AgentError(recoverable=False)`. Do not retry automatically. |
| Mid-conv system rejection | Flip `_supports_mid_conv_system = False`, retry same turn with `<system-reminder>` fallback. One-time. |
| Tool name mismatch | `AgentError(recoverable=True)` + `tool_result(is_error=True)`. Model retries. |
| Malformed tool input | `AgentError(recoverable=True)` + `tool_result(is_error=True)`. Model retries. |
| SDK/network error | `AgentError(recoverable=False)`. Turn aborted. |
| 20 tool calls in one turn | `AgentError(recoverable=False, "cap")`. Turn aborted. |
| Unknown content block type | Silently dropped (not crashed). Forward compatibility. |

### What the Agent Does NOT Do

- **No hardware imports.** Zero `pyhackrf`, `hackrf_agent.hw.*`, `numpy`.
- **No UI imports.** Zero `rich`, `typer`, colored output. Events are typed
  dataclasses; the CLI chooses how to render.
- **No audit logging.** The executor (Part 5) owns the audit log. The agent
  doesn't know audits exist.
- **No approval prompts.** The executor calls `ApprovalPort.request()` internally.
  The agent doesn't know approval exists.
- **No trace ID minting.** The executor mints one per `execute()` call.
- **No raw data to the model.** `CommandResult.data` is passed through as JSON.
  The formatter (Part 5) guarantees JSON-primitive values.

---

## Part 7 Integration Points (COMPLETE)

Part 7's CLI (`hackrf-agent chat`) is implemented in `src/hackrf_agent/cli/chat_cmd.py`.
It assembles all Parts 2–6 into a working product:

1. Constructs `HackrfDriver` (Part 4) — with a real HackRF via lazy import inside
   `_run_chat()`. The `--help` output works without `pyhackrf` installed.
2. Constructs `CommandExecutor` (Part 5) — with `RiskAssessor`, `PermissionService`,
   `AuditService`, `ResultFormatter`, `HackrfDriver`, and `CliApprovalPort`.
3. Constructs `OpenRouterClient` (Part 6) — with the API key from `SettingsService`
   (keychain-backed) and model from `config.toml`.
4. Constructs `HackrfAgent` (Part 6) — injecting `llm`, `executor`, and
   `max_history_messages` from config.
5. Calls `agent.chat(user_message)` in the `_repl` loop, consuming the
   `AgentEvent` stream and rendering each event with `rich`:
   - `AssistantText` → magenta `[agent]` prefix
   - `ToolCallStarted` → dim `→ tool` with justification
   - `ToolCallCompleted` → green `← ok` or red `← fail`
   - `TurnEnded` → yellow `(model refused)` for refusals
   - `AgentError` → red `! error`
6. Provides `CliApprovalPort` (in `approval.py`) — MEDIUM commands get a Y/n
   prompt, HIGH commands require typing the literal string `CONFIRM`. All
   prompts are wrapped in `loop.run_in_executor(None, ...)` to keep the event
   loop responsive.
7. `KillSwitch` (in `kill_switch.py`) wires `SIGINT` (Ctrl-C) to a shared
   `asyncio.Event` + `PermissionService.revoke_all_tx()`. Single tap is
   graceful (abort current operation, return to REPL); double-tap within
   2 seconds is a hard exit.

See **`docs/cli.md`** for the full CLI reference, including command syntax,
approval flow, kill switch semantics, and configuration.

---

## Configuration

| Setting | Default | Where |
|---|---|---|
| Model | `anthropic/claude-sonnet-5` | `OpenRouterClient(model=...)` constructor arg |
| API key | (required) | Constructor arg or `OPENROUTER_API_KEY` env var |
| Max tokens | 4096 | `OpenRouterClient(max_tokens=...)` |
| Rate limit | 30 req / 60 s | `RATE_LIMIT_MAX_REQUESTS`, `RATE_LIMIT_WINDOW_S` constants |
| History cap | 24 messages | `MAX_HISTORY_MESSAGES` in `agent.py` |
| Tool calls per turn | 20 | `HackrfAgent(max_tool_calls_per_turn=...)` |
| Mid-conv system | `True` | `HackrfAgent(supports_mid_conversation_system=...)` — auto-detected |

---

## References

- **OpenRouter API Docs**: [openrouter.ai/docs](https://openrouter.ai/docs)
- **OpenAI Function Calling**: [platform.openai.com/docs/guides/function-calling](https://platform.openai.com/docs/guides/function-calling)
- **`docs/tests.md`** — Part 6 test documentation (llm_client, prompts, agent loop, live)
- **`docs/safety.md`** — BLOCKED bands, risk tiers, FCC citations
- **`docs/development.md`** — Project layout, setup, quality tooling
