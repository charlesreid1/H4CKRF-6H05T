"""A disciplined LLM double that plays back a script of tagged turns.

More structured than ``FakeLLMClient`` — the scripted version takes a list of
tagged turns and builds the responses for you.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hackrf_agent.ai.llm_client import (
    LLMResponse,
    make_text_response,
    make_tool_use_response,
)


@dataclass
class ScriptedLLMClient:
    """LLMClient that plays back a script of turns.

    Each entry in ``script`` is a dict:
      {"type": "text", "text": "...", "stop_reason": "end_turn"}
      {"type": "tool_use", "action": "sweep_spectrum",
       "args": {...}, "justification": "...", "expected_effect": "...",
       "preamble": "..."}   # preamble text is optional

    On each ``send()`` call, one entry is consumed. The recorded call
    history is available as ``.calls`` for assertions.
    """

    script: list[dict[str, Any]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    _index: int = field(default=0, init=False)

    async def send(
        self,
        *,
        system: list[dict[str, Any]] | str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls.append({
            "system": system,
            "messages": [dict(m) for m in messages],
            "tools": list(tools),
            "max_tokens": max_tokens,
        })
        if self._index >= len(self.script):
            raise IndexError(
                f"ScriptedLLMClient: script exhausted after {self._index} turns"
            )
        entry = self.script[self._index]
        self._index += 1
        return self._entry_to_response(entry, self._index)

    @staticmethod
    def _entry_to_response(entry: dict[str, Any], seq: int) -> LLMResponse:
        etype = entry["type"]
        if etype == "text":
            return make_text_response(
                text=entry.get("text", ""),
                stop_reason=entry.get("stop_reason", "end_turn"),
            )
        if etype == "tool_use":
            return make_tool_use_response(
                tool_name="execute_command",
                tool_input={
                    "action": entry["action"],
                    "args": entry.get("args", {}),
                    "justification": entry["justification"],
                    "expected_effect": entry["expected_effect"],
                },
                tool_use_id=f"toolu_scripted_{seq}",
                preamble=entry.get("preamble"),
            )
        raise ValueError(f"unknown scripted entry type: {etype!r}")
