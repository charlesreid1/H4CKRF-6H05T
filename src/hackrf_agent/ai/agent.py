"""The conversation loop — where the LLM and executor boundaries meet.

``HackrfAgent.chat(...)`` ties an ``LLMClient``, a ``CommandExecutor``, and
a ``PermissionService`` together. It yields typed ``AgentEvent`` objects to
the caller (the CLI in Part 7). Zero hardware imports. Zero UI imports.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

from hackrf_agent.ai.llm_client import LLMClient
from hackrf_agent.ai.prompts import (
    EXECUTE_COMMAND_TOOL_SCHEMA,
    MAX_TOOL_CALLS_PER_RESPONSE,
    SYSTEM_PROMPT,
    TOOL_NAME,
)
from hackrf_agent.domain.executor import CommandExecutor
from hackrf_agent.domain.models import (
    CommandAction,
    CommandResult,
    ExecuteCommand,
)
from hackrf_agent.domain.permission_service import PermissionService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_HISTORY_MESSAGES: int = 24
"""Trim the message list to the last N entries before each request.

Empirically enough for a REPL turn; longer conversations live in the
audit log. We NEVER split a tool_use / tool_result pair — see
_trim_history for the pair-safe logic.
"""

# ---------------------------------------------------------------------------
# Event dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssistantText:
    """A text block from the assistant. May appear before or after tool calls."""

    type: Literal["assistant_text"] = "assistant_text"
    text: str = ""


@dataclass(frozen=True)
class ToolCallStarted:
    """Emitted just before the executor runs a command."""

    type: Literal["tool_call_started"] = "tool_call_started"
    action: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    justification: str = ""
    expected_effect: str = ""


@dataclass(frozen=True)
class ToolCallCompleted:
    """Emitted after the executor returns a result."""

    type: Literal["tool_call_completed"] = "tool_call_completed"
    action: str = ""
    result: CommandResult | None = None


@dataclass(frozen=True)
class TurnEnded:
    """The conversation turn has ended (end_turn, refusal, or error)."""

    type: Literal["turn_ended"] = "turn_ended"
    stop_reason: str = ""


@dataclass(frozen=True)
class AgentError:
    """An error during the conversation loop.

    ``recoverable=True`` means the loop continued (e.g. malformed tool
    input — the model gets a chance to fix it). ``recoverable=False``
    means the loop aborted.
    """

    type: Literal["agent_error"] = "agent_error"
    message: str = ""
    recoverable: bool = False


AgentEvent = (
    AssistantText | ToolCallStarted | ToolCallCompleted | TurnEnded | AgentError
)

# ---------------------------------------------------------------------------
# HackrfAgent
# ---------------------------------------------------------------------------


class HackrfAgent:
    """Conversation loop. Owns the message history for one chat session.

    The agent does not own the driver, executor, or audit log — those
    are constructed by the caller (Part 7's CLI) and passed in. The
    agent's only job is:

      1. Build the request (system + trimmed messages + one tool).
      2. Send it via the LLMClient.
      3. If ``stop_reason == "tool_use"``, extract the (at most one)
         ``tool_use`` block, hand it to the executor, append the result
         to messages, loop.
      4. Otherwise (``end_turn`` / ``refusal`` / anything else),
         terminate the turn.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        executor: CommandExecutor,
        permissions: PermissionService,
        max_history_messages: int = MAX_HISTORY_MESSAGES,
        max_tool_calls_per_turn: int = 20,
        supports_mid_conversation_system: bool = True,
    ) -> None:
        self._llm = llm
        self._executor = executor
        self._permissions = permissions
        self._max_history = max_history_messages
        self._max_tool_calls_per_turn = max_tool_calls_per_turn
        self._supports_mid_conv_system = supports_mid_conversation_system
        self._messages: list[dict[str, Any]] = []

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Read-only view of the current message history (for tests / CLI)."""
        return list(self._messages)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def chat(self, user_message: str) -> AsyncIterator[AgentEvent]:
        """Run one user-message → assistant-response turn.

        Yields events in order. Terminates on end_turn, refusal, or an
        unrecoverable error. May yield 0 tool_call_* events (the
        assistant replied without acting) or many (the assistant chained
        several execute_command calls in one turn, one per response).
        """
        # 1. Append the user message.
        self._messages.append({"role": "user", "content": user_message})

        tool_calls_this_turn = 0
        while True:
            # 2. Build the request.
            history = self._trim_history(self._messages)
            grants = await self._permissions.list_active()
            per_turn_system = self._build_per_turn_system(grants)
            if per_turn_system is not None and self._supports_mid_conv_system:
                # Append a mid-conversation system message to the trimmed
                # history. This does NOT go into self._messages (we
                # rebuild it every turn from the live grant list).
                request_messages = history + [per_turn_system]
            elif per_turn_system is not None:
                # Fallback: inject a <system-reminder> into the last
                # user message. Only kicks in if the model rejected
                # mid-conversation system in a prior turn.
                request_messages = self._inject_system_reminder(
                    history, per_turn_system["content"],
                )
            else:
                request_messages = history

            # 3. Send.
            try:
                response = await self._llm.send(
                    system=self._build_top_level_system(),
                    messages=request_messages,
                    tools=[EXECUTE_COMMAND_TOOL_SCHEMA],
                    max_tokens=4096,
                )
            except Exception as e:  # noqa: BLE001 — SDK error taxonomy varies
                # Handle mid-conversation-system rejection specifically.
                if self._is_mid_conv_system_rejection(e):
                    logger.info(
                        "model does not support mid-conversation system; "
                        "falling back to <system-reminder> for this session"
                    )
                    self._supports_mid_conv_system = False
                    continue  # retry the same turn with the fallback
                yield AgentError(
                    message=f"LLM request failed: {type(e).__name__}: {e}",
                    recoverable=False,
                )
                return

            # 4. Yield assistant text blocks in order.
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    yield AssistantText(text=block.text or "")

            # 5. Handle the stop_reason.
            if response.stop_reason == "end_turn":
                # Persist the assistant turn (text only — no tool_use to echo).
                self._append_assistant_turn(response.content)
                yield TurnEnded(stop_reason="end_turn")
                return
            if response.stop_reason == "refusal":
                self._append_assistant_turn(response.content)
                yield TurnEnded(stop_reason="refusal")
                return
            if response.stop_reason != "tool_use":
                yield AgentError(
                    message=(
                        f"unexpected stop_reason {response.stop_reason!r}; "
                        "aborting turn"
                    ),
                    recoverable=False,
                )
                return

            # 6. Extract the tool_use blocks. Cap to
            # MAX_TOOL_CALLS_PER_RESPONSE.
            tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            if not tool_uses:
                yield AgentError(
                    message="stop_reason=tool_use but no tool_use blocks found",
                    recoverable=False,
                )
                return
            if len(tool_uses) > MAX_TOOL_CALLS_PER_RESPONSE:
                logger.warning(
                    "model returned %d tool_use blocks; executing first, "
                    "dropping %d extras",
                    len(tool_uses), len(tool_uses) - MAX_TOOL_CALLS_PER_RESPONSE,
                )
            chosen = tool_uses[0]

            # 7. Persist the assistant turn *with the tool_use block*.
            # We only persist the first tool_use (matching what we
            # executed) so the tool_result on the next turn matches.
            self._append_assistant_turn(
                [b for b in response.content if getattr(b, "type", None) == "text"] +
                [chosen]
            )

            # 8. Dispatch to the executor. Wrong tool name is a bug,
            # not a bypass — refuse structurally.
            if chosen.name != TOOL_NAME:
                error_msg = (
                    f"model requested tool {chosen.name!r}; only "
                    f"{TOOL_NAME!r} is exposed"
                )
                self._messages.append(self._tool_error_message(chosen.id, error_msg))
                yield AgentError(message=error_msg, recoverable=True)
                tool_calls_this_turn += 1
                if tool_calls_this_turn >= self._max_tool_calls_per_turn:
                    yield AgentError(message="tool-call cap reached", recoverable=False)
                    return
                continue

            # 9. Build ExecuteCommand, execute, format tool_result.
            try:
                command = self._build_execute_command(chosen.input)
            except (ValueError, KeyError, TypeError) as e:
                error_msg = f"invalid execute_command input: {type(e).__name__}: {e}"
                self._messages.append(self._tool_error_message(chosen.id, error_msg))
                yield AgentError(message=error_msg, recoverable=True)
                tool_calls_this_turn += 1
                if tool_calls_this_turn >= self._max_tool_calls_per_turn:
                    yield AgentError(message="tool-call cap reached", recoverable=False)
                    return
                continue

            yield ToolCallStarted(
                action=command.action.value,
                args=dict(command.args),
                justification=command.justification,
                expected_effect=command.expected_effect,
            )
            result = await self._executor.execute(command)
            yield ToolCallCompleted(action=command.action.value, result=result)

            # 10. Append the tool_result and loop.
            self._messages.append(self._tool_result_message(chosen.id, result))
            tool_calls_this_turn += 1
            if tool_calls_this_turn >= self._max_tool_calls_per_turn:
                yield AgentError(
                    message=(
                        f"tool-call cap ({self._max_tool_calls_per_turn}) reached; "
                        "ending turn"
                    ),
                    recoverable=False,
                )
                return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_top_level_system(self) -> list[dict[str, Any]]:
        """The stable system prompt, with prompt-cache marker on the last block."""
        return [{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }]

    def _build_per_turn_system(self, grants: list[Any]) -> dict[str, Any] | None:
        """Return a mid-conversation system message describing active grants,
        or None if the grant list is empty (nothing to report)."""
        if not grants:
            return None
        lines = ["Currently active TX grants:"]
        for g in grants:
            lines.append(
                f"- {g.band_start_hz}–{g.band_stop_hz} Hz, "
                f"max_gain_db={g.max_gain_db}, "
                f"expires_at={g.expires_at.isoformat()}"
            )
        return {"role": "system", "content": "\n".join(lines)}

    def _inject_system_reminder(
        self,
        messages: list[dict[str, Any]],
        reminder_text: str,
    ) -> list[dict[str, Any]]:
        """Fallback for models that reject mid-conversation system.

        Wraps ``reminder_text`` in <system-reminder> and appends it to
        the last user message's content. Returns a new list; does NOT
        mutate ``messages``.
        """
        if not messages or messages[-1].get("role") != "user":
            return messages
        out = list(messages)
        last = dict(out[-1])
        block = f"\n\n<system-reminder>\n{reminder_text}\n</system-reminder>"
        if isinstance(last["content"], str):
            last["content"] = last["content"] + block
        elif isinstance(last["content"], list):
            last["content"] = list(last["content"]) + [{"type": "text", "text": block}]
        out[-1] = last
        return out

    def _trim_history(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return the last ``self._max_history`` messages, pair-safe.

        Never splits an assistant turn from its following tool_result
        user turn. If trimming would land in the middle of such a pair,
        drop the pair entirely (both).
        """
        if len(messages) <= self._max_history:
            return list(messages)
        trimmed = messages[-self._max_history:]
        # If the first message in the trimmed window is a tool_result-only
        # user turn, drop it (its assistant parent was cut off).
        while trimmed and self._is_tool_result_only_user(trimmed[0]):
            trimmed = trimmed[1:]
        return trimmed

    @staticmethod
    def _is_tool_result_only_user(msg: dict[str, Any]) -> bool:
        if msg.get("role") != "user":
            return False
        content = msg.get("content")
        if not isinstance(content, list):
            return False
        return all(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content
        )

    def _append_assistant_turn(self, content: list[Any]) -> None:
        """Append the assistant's response to history.

        Serializes each block to a plain dict so the messages list stays
        JSON-friendly (some tests dump it).
        """
        serialized: list[dict[str, Any]] = []
        for block in content:
            btype = getattr(block, "type", None)
            if btype == "text":
                serialized.append({"type": "text", "text": block.text or ""})
            elif btype == "tool_use":
                serialized.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": dict(block.input or {}),
                })
            elif btype == "thinking":
                # We never surface thinking to the user, but preserve
                # the block if the model returns one (Opus 4.8 requires
                # blocks to be echoed back unchanged in continuation).
                serialized.append({
                    "type": "thinking",
                    "thinking": getattr(block, "thinking", ""),
                })
            # Silently drop any unknown block types.
        if serialized:
            self._messages.append({"role": "assistant", "content": serialized})

    def _tool_result_message(
        self,
        tool_use_id: str,
        result: CommandResult,
    ) -> dict[str, Any]:
        """Build the user-role tool_result message from a CommandResult."""
        body = {
            "success": result.success,
            "action": result.action.value,
            "message": result.message,
            "data": result.data,
            "error": result.error,
        }
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": json.dumps(body),
                "is_error": not result.success,
            }],
        }

    def _tool_error_message(
        self,
        tool_use_id: str,
        error_text: str,
    ) -> dict[str, Any]:
        """Build a tool_result signalling an agent-side error to the model."""
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": error_text,
                "is_error": True,
            }],
        }

    @staticmethod
    def _build_execute_command(raw: dict[str, Any] | None) -> ExecuteCommand:
        """Turn the model's tool_use.input into a validated ExecuteCommand.

        Raises ValueError / KeyError / TypeError on shape errors — the
        agent turns those into tool_result(is_error=True) for the model
        to recover from.
        """
        if not isinstance(raw, dict):
            raise ValueError(f"tool input must be a dict, got {type(raw).__name__}")
        action = CommandAction(raw["action"])  # raises ValueError on bad enum
        return ExecuteCommand(
            action=action,
            args=raw.get("args", {}) or {},
            justification=raw.get("justification", "") or "",
            expected_effect=raw.get("expected_effect", "") or "",
        )

    @staticmethod
    def _is_mid_conv_system_rejection(err: Exception) -> bool:
        """Heuristic: does this look like the 'role system not supported'
        400 the API returns on non-Opus-4.8 models?

        We can't rely on ``anthropic`` being imported (fake tests), so
        we string-match on the message. Belt-and-braces the check by
        also looking for HTTP 400.
        """
        msg = str(err).lower()
        return "role 'system' is not supported" in msg or (
            "400" in msg and "system" in msg and "not supported" in msg
        )
