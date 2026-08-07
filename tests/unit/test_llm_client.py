"""Unit tests for llm_client.py — protocol, fake, rate limiter, and request/response translation.

None of these tests call the real OpenRouter API.
"""

import json
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hackrf_agent.ai.llm_client import (
    DEFAULT_MODEL,
    RATE_LIMIT_MAX_REQUESTS,
    RATE_LIMIT_WINDOW_S,
    FakeLLMClient,
    LLMResponse,
    OpenRouterClient,
    _FakeContentBlock,
    make_text_response,
    make_tool_use_response,
)

# ---------------------------------------------------------------------------
# FakeLLMClient tests
# ---------------------------------------------------------------------------


class TestFakeLLMClient:
    """Tests for the FakeLLMClient test double."""

    async def test_fifo_order_three_sends(self) -> None:
        """FakeLLMClient returns queued responses in FIFO order."""
        r1 = make_text_response("first")
        r2 = make_text_response("second")
        r3 = make_text_response("third")
        fake = FakeLLMClient(responses=[r1, r2, r3])

        result1 = await fake.send(system=[], messages=[], tools=[])
        result2 = await fake.send(system=[], messages=[], tools=[])
        result3 = await fake.send(system=[], messages=[], tools=[])

        assert result1.content[0].text == "first"
        assert result2.content[0].text == "second"
        assert result3.content[0].text == "third"

    async def test_records_call_kwargs(self) -> None:
        """FakeLLMClient records each call's kwargs for test assertions."""
        fake = FakeLLMClient(responses=[make_text_response("ok")])

        await fake.send(
            system=[{"type": "text", "text": "sys"}],
            messages=[{"role": "user", "content": "hello"}],
            tools=[{"name": "t1"}],
            max_tokens=100,
        )

        assert len(fake.calls) == 1
        assert fake.calls[0]["system"] == [{"type": "text", "text": "sys"}]
        assert fake.calls[0]["messages"] == [{"role": "user", "content": "hello"}]
        assert fake.calls[0]["tools"] == [{"name": "t1"}]
        assert fake.calls[0]["max_tokens"] == 100

    async def test_empty_queue_raises_index_error(self) -> None:
        """FakeLLMClient with empty queue raises IndexError (not hangs)."""
        fake = FakeLLMClient(responses=[])

        with pytest.raises(IndexError, match="no more queued responses"):
            await fake.send(system=[], messages=[], tools=[])

    async def test_does_not_mutate_inputs(self) -> None:
        """FakeLLMClient does not mutate the messages/tools lists in place."""
        fake = FakeLLMClient(responses=[make_text_response("ok")])
        messages = [{"role": "user", "content": "hi"}]
        tools = [{"name": "t"}]

        await fake.send(system=[], messages=messages, tools=tools)

        # Original lists unchanged.
        assert messages == [{"role": "user", "content": "hi"}]
        assert tools == [{"name": "t"}]


# ---------------------------------------------------------------------------
# Response-building helper tests
# ---------------------------------------------------------------------------


class TestMakeTextResponse:
    """Tests for make_text_response helper."""

    def test_yields_text_block_with_end_turn(self) -> None:
        """make_text_response yields content[0].type=='text' and stop_reason=='end_turn'."""
        resp = make_text_response("hello world")
        assert resp.stop_reason == "end_turn"
        assert len(resp.content) == 1
        assert resp.content[0].type == "text"
        assert resp.content[0].text == "hello world"

    def test_custom_stop_reason(self) -> None:
        """make_text_response accepts a custom stop_reason."""
        resp = make_text_response("nope", stop_reason="refusal")
        assert resp.stop_reason == "refusal"

    def test_raw_is_none(self) -> None:
        """make_text_response sets raw=None (no SDK object needed)."""
        resp = make_text_response("test")
        assert resp.raw is None


class TestMakeToolUseResponse:
    """Tests for make_tool_use_response helper."""

    def test_yields_tool_use_block(self) -> None:
        """make_tool_use_response yields stop_reason=='tool_use' and a tool_use block."""
        resp = make_tool_use_response(
            tool_name="execute_command",
            tool_input={"action": "get_device_info", "args": {}},
        )
        assert resp.stop_reason == "tool_use"
        tool_blocks = [b for b in resp.content if b.type == "tool_use"]
        assert len(tool_blocks) == 1
        assert tool_blocks[0].name == "execute_command"
        assert tool_blocks[0].input["action"] == "get_device_info"

    def test_includes_preamble_text(self) -> None:
        """make_tool_use_response prepends preamble text when given."""
        resp = make_tool_use_response(
            tool_name="execute_command",
            tool_input={"action": "sweep_spectrum"},
            preamble="Let me check the spectrum.",
        )
        text_blocks = [b for b in resp.content if b.type == "text"]
        assert len(text_blocks) == 1
        assert text_blocks[0].text == "Let me check the spectrum."

    def test_default_tool_use_id(self) -> None:
        """make_tool_use_response uses 'toolu_test_1' as default id."""
        resp = make_tool_use_response(
            tool_name="execute_command",
            tool_input={},
        )
        tool_block = [b for b in resp.content if b.type == "tool_use"][0]
        assert tool_block.id == "toolu_test_1"

    def test_custom_tool_use_id(self) -> None:
        """make_tool_use_response accepts a custom tool_use_id."""
        resp = make_tool_use_response(
            tool_name="execute_command",
            tool_input={},
            tool_use_id="toolu_custom_42",
        )
        tool_block = [b for b in resp.content if b.type == "tool_use"][0]
        assert tool_block.id == "toolu_custom_42"


# ---------------------------------------------------------------------------
# OpenRouterClient tests (no real API calls)
# ---------------------------------------------------------------------------


class TestOpenRouterClientConstruction:
    """Tests for OpenRouterClient constructor validation."""

    def test_no_api_key_raises_runtime_error(self) -> None:
        """OpenRouterClient(api_key=None) with no env var raises RuntimeError."""
        # Ensure the env var is not set.
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(RuntimeError, match="no API key"),
        ):
            OpenRouterClient(api_key=None)

    def test_api_key_from_constructor(self) -> None:
        """OpenRouterClient(api_key='sk-fake') constructs without error."""
        # This test verifies we don't open a network connection on construction.
        with patch.dict(os.environ, {}, clear=True):
            client = OpenRouterClient(api_key="sk-fake")
            assert client.model == DEFAULT_MODEL

    def test_api_key_from_env_var(self) -> None:
        """OpenRouterClient falls back to OPENROUTER_API_KEY env var."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-from-env"}, clear=True):
            client = OpenRouterClient()
            assert client.model == DEFAULT_MODEL

    def test_custom_model(self) -> None:
        """OpenRouterClient accepts a custom model string."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test"}, clear=True):
            client = OpenRouterClient(model="anthropic/claude-opus-4-8")
            assert client.model == "anthropic/claude-opus-4-8"

    def test_import_error_when_openai_sdk_missing(self) -> None:
        """OpenRouterClient raises RuntimeError when openai SDK is not installed."""
        with (
            patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test"}, clear=True),
            patch.dict("sys.modules", {"openai": None}),
            patch("builtins.__import__", side_effect=ImportError("no openai")),
            pytest.raises(RuntimeError, match="openai SDK not installed"),
        ):
            OpenRouterClient(api_key="sk-test")


# ---------------------------------------------------------------------------
# Rate limiter tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    """Tests for OpenRouterClient._wait_for_slot."""

    @pytest.fixture
    def client(self) -> OpenRouterClient:
        """Create a client with a fake API key for rate-limit testing."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test"}, clear=True):
            return OpenRouterClient(api_key="sk-test")

    async def test_blocks_at_limit(self, client: OpenRouterClient) -> None:
        """Queue 30 timestamps; the 31st call should sleep before returning."""
        # Fill the deque with 30 recent timestamps.
        now = 1000.0
        for i in range(RATE_LIMIT_MAX_REQUESTS):
            client._timestamps.append(now - i * 0.1)

        # Use a mutable list for the current time so fake_sleep can advance it.
        current_time = [now]
        sleep_calls: list[float] = []

        async def fake_sleep(duration: float) -> None:
            sleep_calls.append(duration)
            # Advance time so the oldest timestamp ages out of the window.
            current_time[0] += duration + RATE_LIMIT_WINDOW_S

        def fake_monotonic() -> float:
            return current_time[0]

        with (
            patch("time.monotonic", new=fake_monotonic),
            patch("asyncio.sleep", new=fake_sleep),
        ):
            await client._wait_for_slot()

        # Since the deque was full and all timestamps are recent,
        # _wait_for_slot should have slept at least once.
        assert len(sleep_calls) >= 1
        assert sleep_calls[0] > 0

    async def test_no_block_when_old_timestamps_expire(
        self,
        client: OpenRouterClient,
    ) -> None:
        """30 timestamps but oldest > 60s old → returns immediately (no sleep)."""
        now = 1000.0
        # All timestamps are older than the window.
        for i in range(RATE_LIMIT_MAX_REQUESTS):
            client._timestamps.append(now - RATE_LIMIT_WINDOW_S - 10.0 - i * 0.1)

        sleep_calls: list[float] = []

        async def fake_sleep(duration: float) -> None:
            sleep_calls.append(duration)

        with (
            patch("time.monotonic", return_value=now),
            patch("asyncio.sleep", new=fake_sleep),
        ):
            await client._wait_for_slot()

        # All old timestamps should have been popped; no sleep needed.
        assert len(sleep_calls) == 0

    async def test_partial_window_cleanup(self, client: OpenRouterClient) -> None:
        """Mix of old and new timestamps — old ones popped, no sleep."""
        now = 1000.0
        # Add 10 old timestamps followed by 10 recent ones.
        for i in range(10):
            client._timestamps.append(now - RATE_LIMIT_WINDOW_S - 5.0 - i)
        for i in range(10):
            client._timestamps.append(now - i * 0.5)

        sleep_calls: list[float] = []

        async def fake_sleep(duration: float) -> None:
            sleep_calls.append(duration)

        with (
            patch("time.monotonic", return_value=now),
            patch("asyncio.sleep", new=fake_sleep),
        ):
            await client._wait_for_slot()

        # 10 old popped, 10 recent remain; 10 < 30 so no sleep.
        assert len(sleep_calls) == 0
        # After cleanup, we should have 10 recent + 1 new = 11 timestamps.
        assert len(client._timestamps) == 11


# ---------------------------------------------------------------------------
# _FakeContentBlock tests
# ---------------------------------------------------------------------------


class TestFakeContentBlock:
    """Tests for the _FakeContentBlock duck-typed content block."""

    def test_text_block_shape(self) -> None:
        """_FakeContentBlock(type='text') has .type and .text attributes."""
        block = _FakeContentBlock(type="text", text="hello")
        assert block.type == "text"
        assert block.text == "hello"
        assert block.name is None
        assert block.input is None
        assert block.id is None

    def test_tool_use_block_shape(self) -> None:
        """_FakeContentBlock(type='tool_use') has .name, .input, .id."""
        block = _FakeContentBlock(
            type="tool_use",
            name="execute_command",
            input={"action": "sweep_spectrum"},
            id="toolu_001",
        )
        assert block.type == "tool_use"
        assert block.name == "execute_command"
        assert block.input == {"action": "sweep_spectrum"}
        assert block.id == "toolu_001"
        assert block.text is None


# ---------------------------------------------------------------------------
# LLMResponse tests
# ---------------------------------------------------------------------------


class TestLLMResponse:
    """Tests for the LLMResponse dataclass."""

    def test_frozen_dataclass(self) -> None:
        """LLMResponse is frozen (immutable)."""
        resp = LLMResponse(stop_reason="end_turn", content=[], raw=None)
        with pytest.raises(AttributeError):
            resp.stop_reason = "changed"  # type: ignore[misc]

    def test_stores_raw_reference(self) -> None:
        """LLMResponse.raw stores an arbitrary object reference."""
        raw_obj = object()
        resp = LLMResponse(stop_reason="end_turn", content=[], raw=raw_obj)
        assert resp.raw is raw_obj


# ---------------------------------------------------------------------------
# Gap 2: Request-translation tests (system flattening, tool_result→tool,
# tool_use→tool_calls).  These mock the OpenAI SDK at the chat.completions
# layer so we can inspect the translated messages without a real API key.
# ---------------------------------------------------------------------------


def _make_mock_completion(
    *,
    finish_reason: str = "stop",
    text: str = "",
    tool_calls: list[dict[str, str]] | None = None,
) -> MagicMock:
    """Build a MagicMock shaped like an OpenAI ChatCompletion response."""

    tc_objects: list[MagicMock] = []
    for tc in (tool_calls or []):
        tc_obj = MagicMock()
        tc_obj.id = tc["id"]
        tc_obj.type = "function"
        tc_obj.function = MagicMock()
        tc_obj.function.name = tc["name"]
        tc_obj.function.arguments = tc["arguments"]
        tc_objects.append(tc_obj)

    choice = MagicMock()
    choice.finish_reason = finish_reason
    choice.message = MagicMock()
    choice.message.content = text
    choice.message.tool_calls = tc_objects if tc_objects else None
    choice.message.refusal = None

    completion = MagicMock()
    completion.choices = [choice]
    return completion


class TestOpenRouterClientSendTranslation:
    """Unit tests for the request-translation logic in OpenRouterClient.send().

    These mock the underlying OpenAI SDK call and assert on the
    translated *request* messages that were sent to the API.  No real
    network — just the translation layer.
    """

    @pytest.fixture
    def client_and_create(self) -> tuple[OpenRouterClient, AsyncMock]:
        """Return (client, mocked_create) with a fake API key."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test"}, clear=True):
            client = OpenRouterClient(api_key="sk-test")
        # Replace the inner AsyncOpenAI client's chat.completions.create
        # with an AsyncMock so we can capture calls + control responses.
        mock_create = AsyncMock()
        client._client.chat.completions.create = mock_create
        return client, mock_create

    # -- system block flattening ------------------------------------------

    async def test_system_list_flattened_to_single_message(
        self,
        client_and_create: tuple[OpenRouterClient, AsyncMock],
    ) -> None:
        """System blocks (list of {type:text,text:...}) are joined with \\n\\n."""
        client, mock_create = client_and_create
        mock_create.return_value = _make_mock_completion(text="ok")

        await client.send(
            system=[
                {"type": "text", "text": "First block."},
                {"type": "text", "text": "Second block."},
            ],
            messages=[{"role": "user", "content": "hello"}],
            tools=[],
        )

        call_args = mock_create.call_args
        # call_args is an async call; use kwargs for keyword args.
        # Depending on SDK version, messages may be positional or keyword.
        # openai SDK passes messages as the first positional arg to create().
        sent_messages: list[dict[str, Any]] = call_args[1]["messages"]
        system_msg = sent_messages[0]
        assert system_msg["role"] == "system"
        assert system_msg["content"] == "First block.\n\nSecond block."

    async def test_system_string_passed_through(
        self,
        client_and_create: tuple[OpenRouterClient, AsyncMock],
    ) -> None:
        """A plain string system prompt is passed through unchanged."""
        client, mock_create = client_and_create
        mock_create.return_value = _make_mock_completion(text="ok")

        await client.send(
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
        )

        sent_messages: list[dict[str, Any]] = mock_create.call_args[1]["messages"]
        system_msg = sent_messages[0]
        assert system_msg["role"] == "system"
        assert system_msg["content"] == "You are a helpful assistant."

    async def test_non_text_system_blocks_are_filtered_out(
        self,
        client_and_create: tuple[OpenRouterClient, AsyncMock],
    ) -> None:
        """System blocks without type=='text' are silently skipped."""
        client, mock_create = client_and_create
        mock_create.return_value = _make_mock_completion(text="ok")

        await client.send(
            system=[
                {"type": "thinking", "thinking": "nope"},
                {"type": "text", "text": "Only this one."},
            ],
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
        )

        sent_messages: list[dict[str, Any]] = mock_create.call_args[1]["messages"]
        system_msg = sent_messages[0]
        assert system_msg["content"] == "Only this one."

    # -- tool_result → role:tool translation ------------------------------

    async def test_tool_result_translated_to_tool_role(
        self,
        client_and_create: tuple[OpenRouterClient, AsyncMock],
    ) -> None:
        """User-message tool_result blocks become role:'tool' messages."""
        client, mock_create = client_and_create
        mock_create.return_value = _make_mock_completion(text="got it")

        await client.send(
            system="sys",
            messages=[
                {"role": "user", "content": "run a command"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_001",
                            "name": "execute_command",
                            "input": {"action": "get_device_info", "args": {}},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_001",
                            "content": '{"success": true, "action": "get_device_info", "data": {"board_id": 2}}',
                            "is_error": False,
                        }
                    ],
                },
            ],
            tools=[],
        )

        sent_messages: list[dict[str, Any]] = mock_create.call_args[1]["messages"]
        # Find the tool-role message.
        tool_msgs = [m for m in sent_messages if m["role"] == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["tool_call_id"] == "toolu_001"
        assert tool_msgs[0]["content"] == (
            '{"success": true, "action": "get_device_info", "data": {"board_id": 2}}'
        )

    async def test_tool_result_with_empty_content(
        self,
        client_and_create: tuple[OpenRouterClient, AsyncMock],
    ) -> None:
        """tool_result block with missing/empty content defaults to ''."""
        client, mock_create = client_and_create
        mock_create.return_value = _make_mock_completion(text="ok")

        await client.send(
            system="sys",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_empty",
                            # no "content" key
                        }
                    ],
                },
            ],
            tools=[],
        )

        sent_messages: list[dict[str, Any]] = mock_create.call_args[1]["messages"]
        tool_msgs = [m for m in sent_messages if m["role"] == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["content"] == ""

    async def test_multiple_tool_results_in_one_user_message(
        self,
        client_and_create: tuple[OpenRouterClient, AsyncMock],
    ) -> None:
        """Multiple tool_result blocks each become their own tool-role message."""
        client, mock_create = client_and_create
        mock_create.return_value = _make_mock_completion(text="done")

        await client.send(
            system="sys",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "id_a",
                            "content": "result_a",
                        },
                        {
                            "type": "tool_result",
                            "tool_use_id": "id_b",
                            "content": "result_b",
                        },
                    ],
                },
            ],
            tools=[],
        )

        sent_messages: list[dict[str, Any]] = mock_create.call_args[1]["messages"]
        tool_msgs = [m for m in sent_messages if m["role"] == "tool"]
        assert len(tool_msgs) == 2
        assert tool_msgs[0]["tool_call_id"] == "id_a"
        assert tool_msgs[0]["content"] == "result_a"
        assert tool_msgs[1]["tool_call_id"] == "id_b"
        assert tool_msgs[1]["content"] == "result_b"

    # -- tool_use → tool_calls translation (assistant response) ------------

    async def test_tool_use_in_assistant_message_becomes_tool_calls(
        self,
        client_and_create: tuple[OpenRouterClient, AsyncMock],
    ) -> None:
        """Assistant-message tool_use blocks become OpenAI tool_calls."""
        client, mock_create = client_and_create
        mock_create.return_value = _make_mock_completion(text="ok")

        await client.send(
            system="sys",
            messages=[
                {"role": "user", "content": "scan 2.4 GHz"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_scan",
                            "name": "execute_command",
                            "input": {"action": "sweep_spectrum", "args": {"start_mhz": 2400, "end_mhz": 2500}},
                        }
                    ],
                },
            ],
            tools=[],
        )

        sent_messages: list[dict[str, Any]] = mock_create.call_args[1]["messages"]
        assistant_msgs = [m for m in sent_messages if m["role"] == "assistant"]
        # There should be at least one assistant message with tool_calls.
        msg_with_tc = [m for m in assistant_msgs if "tool_calls" in m]
        assert len(msg_with_tc) == 1
        tc = msg_with_tc[0]["tool_calls"][0]
        assert tc["id"] == "toolu_scan"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "execute_command"
        assert json.loads(tc["function"]["arguments"]) == {
            "action": "sweep_spectrum",
            "args": {"start_mhz": 2400, "end_mhz": 2500},
        }

    async def test_tool_use_arguments_serialised_to_json_string(
        self,
        client_and_create: tuple[OpenRouterClient, AsyncMock],
    ) -> None:
        """tool_use input dict is JSON-serialised into function.arguments."""
        client, mock_create = client_and_create
        mock_create.return_value = _make_mock_completion(text="ok")

        await client.send(
            system="sys",
            messages=[
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "t1",
                            "name": "execute_command",
                            "input": {"action": "get_device_info", "args": {}},
                        }
                    ],
                },
            ],
            tools=[],
        )

        sent_messages: list[dict[str, Any]] = mock_create.call_args[1]["messages"]
        assistant_msgs = [m for m in sent_messages if m["role"] == "assistant"]
        msg_with_tc = [m for m in assistant_msgs if "tool_calls" in m]
        args_str = msg_with_tc[0]["tool_calls"][0]["function"]["arguments"]
        assert isinstance(args_str, str)
        assert json.loads(args_str) == {"action": "get_device_info", "args": {}}

    async def test_mixed_text_and_tool_use_in_assistant(
        self,
        client_and_create: tuple[OpenRouterClient, AsyncMock],
    ) -> None:
        """Assistant message with text + tool_use: text preserved, tool_use→tool_calls."""
        client, mock_create = client_and_create
        mock_create.return_value = _make_mock_completion(text="ok")

        await client.send(
            system="sys",
            messages=[
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Let me check that."},
                        {
                            "type": "tool_use",
                            "id": "toolu_mixed",
                            "name": "execute_command",
                            "input": {"action": "get_device_info", "args": {}},
                        },
                    ],
                },
            ],
            tools=[],
        )

        sent_messages: list[dict[str, Any]] = mock_create.call_args[1]["messages"]
        assistant_msgs = [m for m in sent_messages if m["role"] == "assistant"]
        msg_with_tc = [m for m in assistant_msgs if "tool_calls" in m]
        assert len(msg_with_tc) == 1
        assert msg_with_tc[0]["content"] == "Let me check that."
        assert len(msg_with_tc[0]["tool_calls"]) == 1

    async def test_assistant_text_only_no_tool_calls(
        self,
        client_and_create: tuple[OpenRouterClient, AsyncMock],
    ) -> None:
        """Assistant message with only text: no tool_calls key."""
        client, mock_create = client_and_create
        mock_create.return_value = _make_mock_completion(text="ok")

        await client.send(
            system="sys",
            messages=[
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Just a reply."},
                    ],
                },
            ],
            tools=[],
        )

        sent_messages: list[dict[str, Any]] = mock_create.call_args[1]["messages"]
        assistant_msgs = [m for m in sent_messages if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1
        assert "tool_calls" not in assistant_msgs[0]
        assert assistant_msgs[0]["content"] == "Just a reply."

    async def test_thinking_blocks_dropped_from_assistant(
        self,
        client_and_create: tuple[OpenRouterClient, AsyncMock],
    ) -> None:
        """Thinking blocks are silently dropped (OpenAI has no slot for them)."""
        client, mock_create = client_and_create
        mock_create.return_value = _make_mock_completion(text="ok")

        await client.send(
            system="sys",
            messages=[
                {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "hmm..."},
                        {"type": "text", "text": "Visible reply."},
                    ],
                },
            ],
            tools=[],
        )

        sent_messages: list[dict[str, Any]] = mock_create.call_args[1]["messages"]
        assistant_msgs = [m for m in sent_messages if m["role"] == "assistant"]
        assert assistant_msgs[0]["content"] == "Visible reply."


# ---------------------------------------------------------------------------
# Gap 1: Malformed tool-call arguments → __raw__ fallback
# ---------------------------------------------------------------------------


class TestOpenRouterClientMalformedToolArgs:
    """Unit test for the JSONDecodeError guardrail in OpenRouterClient.send().

    When the API returns a tool_call with arguments that aren't valid JSON,
    the client catches json.JSONDecodeError and stores the raw string under
    ``{"__raw__": ...}`` so the agent can yield AgentError(recoverable=True)
    instead of crashing the loop.
    """

    @pytest.fixture
    def client(self) -> OpenRouterClient:
        """Return a client with a fake API key + mocked create."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test"}, clear=True):
            c = OpenRouterClient(api_key="sk-test")
        c._client.chat.completions.create = AsyncMock()
        return c

    def test_malformed_json_becomes_raw_fallback(self, client: OpenRouterClient) -> None:
        """tool_call with unparseable arguments → input={'__raw__': '...'}."""
        # Build a completion with a tool_call whose arguments are not valid JSON.
        bad_args = "not valid json {{{"
        mock_completion = _make_mock_completion(
            finish_reason="tool_calls",
            tool_calls=[
                {
                    "id": "call_bad",
                    "name": "execute_command",
                    "arguments": bad_args,
                }
            ],
        )
        client._client.chat.completions.create.return_value = mock_completion

        # We need to run the async send() — use asyncio.run().
        import asyncio

        response: LLMResponse = asyncio.run(
            client.send(
                system="sys",
                messages=[{"role": "user", "content": "do something"}],
                tools=[],
            )
        )

        assert response.stop_reason == "tool_use"
        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        assert len(tool_blocks) == 1
        assert tool_blocks[0].input == {"__raw__": bad_args}
        assert tool_blocks[0].name == "execute_command"
        assert tool_blocks[0].id == "call_bad"

    def test_valid_json_parsed_normally(self, client: OpenRouterClient) -> None:
        """Valid JSON tool_call arguments are parsed as a dict (no __raw__)."""
        import asyncio

        mock_completion = _make_mock_completion(
            finish_reason="tool_calls",
            tool_calls=[
                {
                    "id": "call_good",
                    "name": "execute_command",
                    "arguments": '{"action": "get_device_info", "args": {}}',
                }
            ],
        )
        client._client.chat.completions.create.return_value = mock_completion

        response: LLMResponse = asyncio.run(
            client.send(
                system="sys",
                messages=[{"role": "user", "content": "info"}],
                tools=[],
            )
        )

        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        assert len(tool_blocks) == 1
        assert tool_blocks[0].input == {"action": "get_device_info", "args": {}}
        assert "__raw__" not in tool_blocks[0].input

    def test_empty_arguments_default_to_empty_dict(self, client: OpenRouterClient) -> None:
        """None/empty arguments → {} (no crash, no __raw__)."""
        import asyncio

        mock_completion = _make_mock_completion(
            finish_reason="tool_calls",
            tool_calls=[
                {
                    "id": "call_empty",
                    "name": "execute_command",
                    "arguments": "",
                }
            ],
        )
        client._client.chat.completions.create.return_value = mock_completion

        response: LLMResponse = asyncio.run(
            client.send(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
            )
        )

        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        assert len(tool_blocks) == 1
        assert tool_blocks[0].input == {}
