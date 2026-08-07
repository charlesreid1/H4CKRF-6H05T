"""LLM client protocol + OpenRouter implementation + test doubles.

Thin wrapper around the ``openai`` SDK pointed at the OpenRouter API
with a local rate limiter.  Also exports ``FakeLLMClient`` and
response-building helpers for tests.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol

# ``openai`` is imported lazily inside OpenRouterClient so tests that only
# exercise FakeLLMClient do not require the package to be installed.

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL: str = "deepseek/deepseek-v4-pro"
DEFAULT_MAX_TOKENS: int = 4096
RATE_LIMIT_WINDOW_S: float = 60.0
RATE_LIMIT_MAX_REQUESTS: int = 30

# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMResponse:
    """Wire-model-agnostic response envelope.

    ``raw`` is the SDK's Message object (or the fake stand-in). Callers
    that need typed access poke at ``raw`` directly; everything the loop
    needs is on the top-level fields.
    """

    stop_reason: str
    content: list[Any]  # list of content blocks (text / tool_use / thinking)
    raw: Any


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class LLMClient(Protocol):
    """Send a Messages-API request; get a response back.

    Implementations MUST:
      - Enforce the local 30 req / 60 s cap.
      - Be safe to call concurrently from an ``asyncio`` context, though
        callers won't in practice (the agent loop is sequential).
      - Never mutate ``messages`` or ``tools`` in place.
    """

    async def send(
        self,
        *,
        system: list[dict[str, Any]] | str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> LLMResponse: ...


# ---------------------------------------------------------------------------
# OpenRouterClient
# ---------------------------------------------------------------------------


class OpenRouterClient:
    """Concrete LLMClient backed by the ``openai`` SDK pointed at OpenRouter.

    Local rate limit: at most 30 requests per rolling 60-second window.
    On saturation ``send`` awaits until the window clears; it does NOT
    raise. Retries for 429/5xx are handled by the SDK's own
    ``max_retries=2`` default — do not layer a second loop.

    Translates between the internal Anthropic-shaped ``LLMResponse``
    envelope (kept for minimal agent-loop churn) and the OpenAI Chat
    Completions wire format that OpenRouter exposes.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        try:
            import openai
        except ImportError as e:
            raise RuntimeError(
                "openai SDK not installed; run `pip install hackrf-agent[openrouter]`"
            ) from e
        self._openai = openai
        key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("no API key: pass api_key= or set OPENROUTER_API_KEY")
        self._client = openai.AsyncOpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/charlesreid/hackrf-agent",
                "X-Title": "hackrf-agent",
            },
        )
        self._model = model
        self._max_tokens = max_tokens
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    @property
    def model(self) -> str:
        return self._model

    async def _wait_for_slot(self) -> None:
        """Block until we can make another request within the rolling window.

        Uses a rolling window of ``RATE_LIMIT_WINDOW_S`` seconds and at most
        ``RATE_LIMIT_MAX_REQUESTS`` entries. The sleep is inside the lock
        because the agent loop is single-consumer — if fan-out is added later,
        rewrite with ``asyncio.Condition`` and move the sleep outside the
        critical section.
        """
        async with self._lock:
            while True:
                now = time.monotonic()
                # Drop timestamps older than the window.
                while self._timestamps and now - self._timestamps[0] > RATE_LIMIT_WINDOW_S:
                    self._timestamps.popleft()
                if len(self._timestamps) < RATE_LIMIT_MAX_REQUESTS:
                    self._timestamps.append(now)
                    return
                # Sleep until the oldest slot ages out.
                wait_s = RATE_LIMIT_WINDOW_S - (now - self._timestamps[0]) + 0.01
                logger.info("LLM rate limit hit; sleeping %.2fs", wait_s)
                await asyncio.sleep(wait_s)

    async def send(
        self,
        *,
        system: list[dict[str, Any]] | str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int | None = None,
    ) -> LLMResponse:
        await self._wait_for_slot()

        # -- build OpenAI-format messages list ---------------------------------
        openai_messages: list[dict[str, Any]] = []

        # 1. Prepend a system message.
        if isinstance(system, list):
            system_text = "\n\n".join(
                block["text"] for block in system if block.get("type") == "text"
            )
        else:
            system_text = system
        openai_messages.append({"role": "system", "content": system_text})

        # 2. Translate conversation messages.
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                if isinstance(content, str):
                    openai_messages.append({"role": "user", "content": content})
                elif isinstance(content, list):
                    for block in content:
                        if block.get("type") == "tool_result":
                            openai_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": block["tool_use_id"],
                                    "content": block.get("content", ""),
                                }
                            )

            elif role == "assistant":
                if isinstance(content, list):
                    text_parts: list[str] = []
                    tool_calls: list[dict[str, Any]] = []
                    for block in content:
                        btype = block.get("type")
                        if btype == "text":
                            text_parts.append(block.get("text", ""))
                        elif btype == "tool_use":
                            tool_calls.append(
                                {
                                    "id": block["id"],
                                    "type": "function",
                                    "function": {
                                        "name": block["name"],
                                        "arguments": json.dumps(block.get("input", {})),
                                    },
                                }
                            )
                        # thinking blocks are dropped — OpenAI has no slot
                    assistant_msg: dict[str, Any] = {"role": "assistant"}
                    if text_parts:
                        assistant_msg["content"] = "\n\n".join(text_parts)
                    else:
                        assistant_msg["content"] = None
                    if tool_calls:
                        assistant_msg["tool_calls"] = tool_calls
                    openai_messages.append(assistant_msg)

        # 3. Send to OpenRouter.
        completion = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens or self._max_tokens,
            messages=openai_messages,
            tools=tools,
        )

        # 4. Translate the OpenAI response back into an LLMResponse.
        choice = completion.choices[0]
        finish_reason = choice.finish_reason or "stop"

        # Map finish_reason → internal stop_reason.
        if finish_reason == "stop":
            stop_reason = "end_turn"
        elif finish_reason == "tool_calls":
            stop_reason = "tool_use"
        elif finish_reason == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = finish_reason

        # Check for a refusal field (some providers emit this).
        refusal = getattr(choice.message, "refusal", None)
        if refusal:
            stop_reason = "refusal"

        # Build internal content blocks.
        content_blocks: list[Any] = []

        text = choice.message.content or ""
        if refusal:
            text = refusal
        if text:
            content_blocks.append(_FakeContentBlock(type="text", text=text))

        for tc in choice.message.tool_calls or []:
            try:
                args = (
                    json.loads(tc.function.arguments)
                    if tc.function.arguments
                    else {}
                )
            except json.JSONDecodeError:
                args = {"__raw__": tc.function.arguments}
            content_blocks.append(
                _FakeContentBlock(
                    type="tool_use",
                    id=tc.id,
                    name=tc.function.name,
                    input=args,
                )
            )

        return LLMResponse(
            stop_reason=stop_reason,
            content=content_blocks,
            raw=completion,
        )


# ---------------------------------------------------------------------------
# FakeLLMClient
# ---------------------------------------------------------------------------


@dataclass
class FakeLLMClient:
    """Test double: returns queued responses; records every call.

    Populate ``responses`` in test setup with pre-built ``LLMResponse``
    objects. Each ``send()`` pops from the head. If empty, raises
    ``IndexError`` (fail loud in tests — don't hang).

    ``.calls`` is a list of ``dict`` snapshots of the kwargs passed to
    each ``send()``. Tests assert on this.
    """

    responses: list[LLMResponse] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def send(
        self,
        *,
        system: list[dict[str, Any]] | str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "system": system,
                "messages": [dict(m) for m in messages],
                "tools": list(tools),
                "max_tokens": max_tokens,
            }
        )
        if not self.responses:
            raise IndexError("FakeLLMClient: no more queued responses")
        return self.responses.pop(0)


# ---------------------------------------------------------------------------
# Response-building helpers for tests
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeContentBlock:
    """A minimal duck-typed content block: matches the SDK's shape
    (``.type``, ``.text``, ``.name``, ``.input``, ``.id``) closely enough
    for the agent loop's type-dispatching to work.
    """

    type: str
    text: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None
    id: str | None = None


def make_text_response(text: str, stop_reason: str = "end_turn") -> LLMResponse:
    """Build a canned text-only response (no tool_use)."""
    return LLMResponse(
        stop_reason=stop_reason,
        content=[_FakeContentBlock(type="text", text=text)],
        raw=None,
    )


def make_tool_use_response(
    *,
    tool_name: str,
    tool_input: dict[str, Any],
    tool_use_id: str = "toolu_test_1",
    preamble: str | None = None,
) -> LLMResponse:
    """Build a canned tool_use response with optional preamble text."""
    content: list[Any] = []
    if preamble:
        content.append(_FakeContentBlock(type="text", text=preamble))
    content.append(
        _FakeContentBlock(
            type="tool_use",
            name=tool_name,
            input=tool_input,
            id=tool_use_id,
        )
    )
    return LLMResponse(stop_reason="tool_use", content=content, raw=None)
