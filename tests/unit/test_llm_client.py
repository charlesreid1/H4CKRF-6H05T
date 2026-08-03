"""Unit tests for llm_client.py — protocol, fake, rate limiter.

None of these tests call the real Anthropic API.
"""

import os
from unittest.mock import patch

import pytest

from hackrf_agent.ai.llm_client import (
    RATE_LIMIT_MAX_REQUESTS,
    RATE_LIMIT_WINDOW_S,
    AnthropicClient,
    FakeLLMClient,
    LLMResponse,
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
# AnthropicClient tests (no real API calls)
# ---------------------------------------------------------------------------


class TestAnthropicClientConstruction:
    """Tests for AnthropicClient constructor validation."""

    def test_no_api_key_raises_runtime_error(self) -> None:
        """AnthropicClient(api_key=None) with no env var raises RuntimeError."""
        # Ensure the env var is not set.
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(RuntimeError, match="no API key"),
        ):
            AnthropicClient(api_key=None)

    def test_api_key_from_constructor(self) -> None:
        """AnthropicClient(api_key='sk-fake') constructs without error."""
        # This test verifies we don't open a network connection on construction.
        with patch.dict(os.environ, {}, clear=True):
            client = AnthropicClient(api_key="sk-fake")
            assert client.model == "claude-sonnet-5"

    def test_api_key_from_env_var(self) -> None:
        """AnthropicClient falls back to ANTHROPIC_API_KEY env var."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-from-env"}, clear=True):
            client = AnthropicClient()
            assert client.model == "claude-sonnet-5"

    def test_custom_model(self) -> None:
        """AnthropicClient accepts a custom model string."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=True):
            client = AnthropicClient(model="claude-opus-4-8")
            assert client.model == "claude-opus-4-8"

    def test_import_error_when_anthropic_missing(self) -> None:
        """AnthropicClient raises RuntimeError when anthropic SDK is not installed."""
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=True),
            patch.dict("sys.modules", {"anthropic": None}),
            patch("builtins.__import__", side_effect=ImportError("no anthropic")),
            pytest.raises(RuntimeError, match="anthropic SDK not installed"),
        ):
            AnthropicClient(api_key="sk-test")


# ---------------------------------------------------------------------------
# Rate limiter tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    """Tests for AnthropicClient._wait_for_slot."""

    @pytest.fixture
    def client(self) -> AnthropicClient:
        """Create a client with a fake API key for rate-limit testing."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=True):
            return AnthropicClient(api_key="sk-test")

    async def test_blocks_at_limit(self, client: AnthropicClient) -> None:
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
        self, client: AnthropicClient,
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

    async def test_partial_window_cleanup(self, client: AnthropicClient) -> None:
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
