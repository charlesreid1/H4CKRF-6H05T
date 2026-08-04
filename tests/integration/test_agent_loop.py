"""Integration tests for agent.py — the full agent loop.

All tests use FakeLLMClient with a real CommandExecutor / FakeDriver.
The audit DB is touched, hence "integration".
"""

import logging
from pathlib import Path

import pytest

from hackrf_agent.ai.agent import (
    MAX_HISTORY_MESSAGES,
    AgentError,
    AssistantText,
    HackrfAgent,
    ToolCallCompleted,
    ToolCallStarted,
    TurnEnded,
)
from hackrf_agent.ai.llm_client import (
    FakeLLMClient,
    make_text_response,
    make_tool_use_response,
)
from hackrf_agent.ai.prompts import EXECUTE_COMMAND_TOOL_SCHEMA, SYSTEM_PROMPT
from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.approval import FakeApprovalPort
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.executor import CommandExecutor
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.result_formatter import ResultFormatter
from hackrf_agent.domain.risk_assessor import RiskAssessor
from hackrf_agent.domain.session import new_session
from tests.support.fake_driver import FakeDriver

# ---------------------------------------------------------------------------
# Bench fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def bench(tmp_path: Path):
    """Create a HackrfAgent wired to a FakeLLMClient + FakeDriver + real executor."""
    db = tmp_path / "agent.db"
    await ensure_schema(db)
    driver = FakeDriver()
    approval = FakeApprovalPort(answer=True)
    perms = PermissionService(db)
    llm = FakeLLMClient()
    async with AuditService(db) as audit:
        session = new_session(tmp_path / "sessions")
        executor = CommandExecutor(
            session_id="s1",
            risk_assessor=RiskAssessor(),
            permissions=perms,
            audit=audit,
            driver=driver,
            formatter=ResultFormatter(),
            approval=approval,
            session_paths=session,
        )
        agent = HackrfAgent(llm=llm, executor=executor)
        yield {
            "agent": agent,
            "llm": llm,
            "driver": driver,
            "approval": approval,
            "executor": executor,
            "perms": perms,
            "session": session,
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def collect_events(agent: HackrfAgent, message: str) -> list:
    """Collect all events from agent.chat() into a list."""
    events = []
    async for ev in agent.chat(message):
        events.append(ev)
    return events


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestSimpleTextTurn:
    """Test 1: Single text response with end_turn."""

    async def test_single_text_response_then_end_turn(self, bench) -> None:
        """Queue a text response → yields AssistantText then TurnEnded."""
        bench["llm"].responses = [
            make_text_response("Hello! How can I help?"),
        ]
        events = await collect_events(bench["agent"], "hello")

        assert len(events) == 2
        assert isinstance(events[0], AssistantText)
        assert events[0].text == "Hello! How can I help?"
        assert isinstance(events[1], TurnEnded)
        assert events[1].stop_reason == "end_turn"


class TestSingleToolCall:
    """Test 2: One tool_use(get_device_info) then end_turn."""

    async def test_tool_call_then_end_turn(self, bench) -> None:
        """LLM emits tool_use(get_device_info), then end_turn after result."""
        bench["llm"].responses = [
            make_tool_use_response(
                tool_name="execute_command",
                tool_input={
                    "action": "get_device_info",
                    "args": {},
                    "justification": "Read the device info.",
                    "expected_effect": "Return serial and firmware version.",
                },
                tool_use_id="toolu_1",
            ),
            make_text_response("Device info read successfully."),
        ]
        events = await collect_events(bench["agent"], "read device info")

        # Sequence: ToolCallStarted, ToolCallCompleted, AssistantText, TurnEnded
        assert any(isinstance(e, ToolCallStarted) for e in events)
        assert any(isinstance(e, ToolCallCompleted) for e in events)
        assert any(isinstance(e, TurnEnded) for e in events)

        # Verify the tool call was executed.
        tc = [e for e in events if isinstance(e, ToolCallStarted)][0]
        assert tc.action == "get_device_info"

        tcomp = [e for e in events if isinstance(e, ToolCallCompleted)][0]
        assert tcomp.result is not None
        assert tcomp.result.success is True

        # Driver was called once.
        assert len(bench["driver"].calls) == 1
        assert bench["driver"].calls[0][0] == "get_device_info"


class TestChainedToolCalls:
    """Test 3: Two chained tool_use calls in one turn."""

    async def test_two_chained_tool_calls(self, bench) -> None:
        """LLM emits tool_use → after result, another tool_use → then end_turn."""
        bench["llm"].responses = [
            make_tool_use_response(
                tool_name="execute_command",
                tool_input={
                    "action": "get_device_info",
                    "args": {},
                    "justification": "Step 1: read device info.",
                    "expected_effect": "Return serial and firmware.",
                },
                tool_use_id="toolu_1",
            ),
            make_tool_use_response(
                tool_name="execute_command",
                tool_input={
                    "action": "grant_list",
                    "args": {},
                    "justification": "Step 2: check active grants.",
                    "expected_effect": "Return the list of active TX grants.",
                },
                tool_use_id="toolu_2",
            ),
            make_text_response("All done."),
        ]
        events = await collect_events(bench["agent"], "read device info and grants")

        tc_started = [e for e in events if isinstance(e, ToolCallStarted)]
        tc_completed = [e for e in events if isinstance(e, ToolCallCompleted)]

        # Two pairs.
        assert len(tc_started) == 2
        assert len(tc_completed) == 2
        assert tc_started[0].action == "get_device_info"
        assert tc_started[1].action == "grant_list"

        # Turn ends normally.
        assert events[-1].type == "turn_ended"
        assert events[-1].stop_reason == "end_turn"


class TestMultipleToolUseBlocks:
    """Test 4: Two tool_use blocks in one response — only first executed."""

    async def test_multiple_tool_use_only_first_executed(self, bench, caplog) -> None:
        """Two tool_use blocks in one response: only first executed, warning logged."""
        # Build a response with two tool_use blocks manually.
        from hackrf_agent.ai.llm_client import _FakeContentBlock

        multi = make_tool_use_response(
            tool_name="execute_command",
            tool_input={
                "action": "get_device_info",
                "args": {},
                "justification": "First action.",
                "expected_effect": "Return info.",
            },
            tool_use_id="toolu_a",
        )
        # Append a second tool_use block.
        multi.content.append(
            _FakeContentBlock(
                type="tool_use",
                name="execute_command",
                input={
                    "action": "grant_list",
                    "args": {},
                    "justification": "Second action.",
                    "expected_effect": "Return grants.",
                },
                id="toolu_b",
            )
        )
        # After the tool_result, the model sends end_turn.
        bench["llm"].responses = [
            multi,
            make_text_response("Done."),
        ]

        with caplog.at_level(logging.WARNING):
            events = await collect_events(bench["agent"], "do two things")

        # Only one tool call executed.
        tc_started = [e for e in events if isinstance(e, ToolCallStarted)]
        assert len(tc_started) == 1
        assert tc_started[0].action == "get_device_info"

        # Warning was logged about dropping extra tool_use blocks.
        assert any("dropping" in r.message.lower() for r in caplog.records)

        # Only one driver call.
        assert len(bench["driver"].calls) == 1


class TestRefusal:
    """Test 5: LLM returns stop_reason == 'refusal'."""

    async def test_refusal_stops_turn(self, bench) -> None:
        """stop_reason=='refusal' → TurnEnded(refusal), no tool call attempted."""
        bench["llm"].responses = [
            make_text_response("I cannot do that.", stop_reason="refusal"),
        ]
        events = await collect_events(bench["agent"], "do something bad")

        assert any(e.type == "turn_ended" and e.stop_reason == "refusal" for e in events)
        # No tool calls were made.
        assert not any(isinstance(e, ToolCallStarted) for e in events)
        assert len(bench["driver"].calls) == 0


class TestWrongToolName:
    """Test 6: Model calls a tool we didn't expose."""

    async def test_wrong_tool_name_yields_recoverable_error(self, bench) -> None:
        """tool_use with name='not_execute_command' → AgentError(recoverable=True)."""
        bench["llm"].responses = [
            make_tool_use_response(
                tool_name="not_execute_command",
                tool_input={"action": "get_device_info"},
                tool_use_id="toolu_x",
            ),
            make_text_response("Let me try the right tool."),
        ]
        events = await collect_events(bench["agent"], "do something")

        errors = [e for e in events if isinstance(e, AgentError)]
        assert len(errors) >= 1
        assert errors[0].recoverable is True
        assert "not_execute_command" in errors[0].message

        # The loop continues and ends normally.
        assert events[-1].type == "turn_ended"


class TestMalformedToolInput:
    """Test 7: Model sends malformed input (missing justification)."""

    async def test_missing_justification_yields_recoverable_error(self, bench) -> None:
        """tool_use input missing 'justification' → AgentError(recoverable=True)."""
        bench["llm"].responses = [
            make_tool_use_response(
                tool_name="execute_command",
                tool_input={
                    "action": "get_device_info",
                    "args": {},
                    # justification missing
                    "expected_effect": "Return info.",
                },
                tool_use_id="toolu_bad",
            ),
            make_text_response("Let me fix my input."),
        ]
        events = await collect_events(bench["agent"], "do something")

        errors = [e for e in events if isinstance(e, AgentError)]
        assert len(errors) >= 1
        assert errors[0].recoverable is True
        # The error should mention the validation issue.
        msg_lower = errors[0].message.lower()
        assert "invalid" in msg_lower or "validation" in msg_lower or "value" in msg_lower

        # Loop continues.
        assert events[-1].type == "turn_ended"

    async def test_bad_action_enum_value(self, bench) -> None:
        """tool_use with invalid action enum → AgentError(recoverable=True)."""
        bench["llm"].responses = [
            make_tool_use_response(
                tool_name="execute_command",
                tool_input={
                    "action": "nonexistent_action",
                    "args": {},
                    "justification": "test",
                    "expected_effect": "test",
                },
                tool_use_id="toolu_bad2",
            ),
            make_text_response("Fixed."),
        ]
        events = await collect_events(bench["agent"], "do something")

        errors = [e for e in events if isinstance(e, AgentError)]
        assert len(errors) >= 1
        assert errors[0].recoverable is True


class TestBlockedAction:
    """Test 8: LLM requests a BLOCKED action — executor refuses."""

    async def test_blocked_transmit_yields_failure(self, bench) -> None:
        """Transmit on 1090 MHz → ToolCallCompleted with success=False."""
        bench["llm"].responses = [
            make_tool_use_response(
                tool_name="execute_command",
                tool_input={
                    "action": "transmit_iq",
                    "args": {
                        "center_freq_hz": 1090000000,
                        "tx_vga_gain_db": 20,
                        "iq_path": "/tmp/fake.iq",
                    },
                    "justification": "Testing blocked band.",
                    "expected_effect": "Should be blocked.",
                },
                tool_use_id="toolu_blocked",
            ),
            make_text_response("That was blocked."),
        ]
        events = await collect_events(bench["agent"], "transmit at 1090")

        completed = [e for e in events if isinstance(e, ToolCallCompleted)]
        assert len(completed) == 1
        assert completed[0].result is not None
        assert completed[0].result.success is False
        assert completed[0].result.message.startswith("Action blocked")

        # Driver.transmit_iq was NOT called.
        assert not any(c[0] == "transmit_iq" for c in bench["driver"].calls)


class TestGrantsNotLeakedToLLM:
    """The LLM never sees grant state — it's enforced by the executor's
    risk gate, and the LLM discovers scope by trying and being told."""

    async def test_active_grants_do_not_appear_in_request(self, bench) -> None:
        """Even with active grants, the request contains no grant text."""
        await bench["perms"].grant(
            kind="tx",
            band_start_hz=433_000_000,
            band_stop_hz=434_000_000,
            max_gain_db=30,
            ttl_seconds=3600,
        )

        bench["llm"].responses = [make_text_response("Got it.")]
        await collect_events(bench["agent"], "hello")

        messages = bench["llm"].calls[0]["messages"]
        for msg in messages:
            content_str = str(msg.get("content", ""))
            assert "grant" not in content_str.lower()
            assert "<system-reminder>" not in content_str
            assert msg.get("role") != "system"


class TestHistoryTrimming:
    """Test 11: History trimming — message count stays bounded."""

    async def test_history_trimmed_to_max(self, bench) -> None:
        """After many turns, request messages are trimmed to MAX_HISTORY_MESSAGES."""
        agent = bench["agent"]
        llm: FakeLLMClient = bench["llm"]

        # Send 30 user messages, each getting a text response.
        for i in range(30):
            llm.responses = [make_text_response(f"Reply {i}")]
            await collect_events(agent, f"Message {i}")

        # History should have 60 entries (30 user + 30 assistant).
        assert len(agent.messages) == 60

        # The 31st chat — request should be trimmed.
        llm.responses = [make_text_response("Reply 31")]
        await collect_events(agent, "Message 31")

        # The last call's messages should be ≤ MAX_HISTORY_MESSAGES.
        last_call_messages = llm.calls[-1]["messages"]
        assert len(last_call_messages) <= MAX_HISTORY_MESSAGES


class TestPairSafety:
    """Test 12: Pair-safe trimming — tool_use/tool_result pairs not split."""

    async def test_tool_result_not_orphaned(self, bench) -> None:
        """Orphaned tool_result is dropped when its assistant parent is trimmed."""
        agent = bench["agent"]
        llm: FakeLLMClient = bench["llm"]

        # Seed history: manually inject a tool_use → tool_result pair.
        agent._messages.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_seed",
                        "name": "execute_command",
                        "input": {
                            "action": "get_device_info",
                            "args": {},
                            "justification": "seed",
                            "expected_effect": "seed",
                        },
                    }
                ],
            }
        )
        agent._messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_seed",
                        "content": '{"success": true}',
                        "is_error": False,
                    }
                ],
            }
        )

        # Send enough messages to push history past the trim point.
        # We need more than MAX_HISTORY_MESSAGES so trimming kicks in.
        needed = MAX_HISTORY_MESSAGES - len(agent._messages) + 5
        for i in range(needed):
            llm.responses = [make_text_response(f"R{i}")]
            await collect_events(agent, f"Msg {i}")

        # The last call's messages should not start with a tool_result-only user turn.
        last_messages = llm.calls[-1]["messages"]
        if last_messages:
            first = last_messages[0]
            # If it's a user message, it should not be tool_result-only.
            if first.get("role") == "user":
                content = first.get("content")
                if isinstance(content, list):
                    is_tool_result_only = all(
                        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
                    )
                    assert not is_tool_result_only, (
                        "First message should not be an orphaned tool_result"
                    )


class TestRunawayProtection:
    """Test 13: Runaway protection — cap at 20 tool calls per turn."""

    async def test_tool_call_cap_stops_loop(self, bench) -> None:
        """After 20 tool calls, the agent yields AgentError(recoverable=False)."""
        # Queue 25 tool_use responses — the agent should stop at 20.
        responses = []
        for i in range(25):
            responses.append(
                make_tool_use_response(
                    tool_name="execute_command",
                    tool_input={
                        "action": "get_device_info",
                        "args": {},
                        "justification": f"Call {i}",
                        "expected_effect": "Return info.",
                    },
                    tool_use_id=f"toolu_{i}",
                )
            )

        bench["llm"].responses = responses
        events = await collect_events(bench["agent"], "do many things")

        # Count tool calls.
        tc_started = [e for e in events if isinstance(e, ToolCallStarted)]
        assert len(tc_started) == 20

        # Last error should be the cap message.
        errors = [e for e in events if isinstance(e, AgentError) and not e.recoverable]
        assert len(errors) >= 1
        assert "cap" in errors[-1].message.lower()


class TestSystemPromptAndTools:
    """Tests 15 & 16: System prompt and tool schema are always included."""

    async def test_system_prompt_included(self, bench) -> None:
        """Every request includes the SYSTEM_PROMPT with cache_control."""
        bench["llm"].responses = [make_text_response("Hi")]
        await collect_events(bench["agent"], "hello")

        system = bench["llm"].calls[0]["system"]
        assert isinstance(system, list)
        assert len(system) == 1
        assert system[0]["text"] == SYSTEM_PROMPT
        assert system[0]["cache_control"] == {"type": "ephemeral"}

    async def test_tool_schema_included(self, bench) -> None:
        """Every request includes EXECUTE_COMMAND_TOOL_SCHEMA as the sole tool."""
        bench["llm"].responses = [make_text_response("Hi")]
        await collect_events(bench["agent"], "hello")

        tools = bench["llm"].calls[0]["tools"]
        assert tools == [EXECUTE_COMMAND_TOOL_SCHEMA]

    async def test_system_prompt_and_tools_across_multiple_calls(self, bench) -> None:
        """System prompt and tool schema are present across multiple LLM calls."""
        bench["llm"].responses = [
            make_tool_use_response(
                tool_name="execute_command",
                tool_input={
                    "action": "get_device_info",
                    "args": {},
                    "justification": "Read info.",
                    "expected_effect": "Return info.",
                },
                tool_use_id="toolu_1",
            ),
            make_text_response("Done."),
        ]
        await collect_events(bench["agent"], "read device")

        # Both calls should have the system prompt and tool schema.
        for call in bench["llm"].calls:
            assert call["system"][0]["text"] == SYSTEM_PROMPT
            assert call["tools"] == [EXECUTE_COMMAND_TOOL_SCHEMA]


class TestUnexpectedStopReason:
    """Additional test: unexpected stop_reason yields AgentError."""

    async def test_unexpected_stop_reason(self, bench) -> None:
        """stop_reason='max_tokens' → AgentError(recoverable=False)."""
        bench["llm"].responses = [
            make_text_response("cut off...", stop_reason="max_tokens"),
        ]
        events = await collect_events(bench["agent"], "hello")

        errors = [e for e in events if isinstance(e, AgentError) and not e.recoverable]
        assert len(errors) >= 1
        assert "max_tokens" in errors[0].message.lower()


class TestToolUseNoBlocks:
    """Additional test: stop_reason='tool_use' but no tool_use blocks."""

    async def test_tool_use_stop_reason_without_blocks(self, bench) -> None:
        """stop_reason='tool_use' without tool_use blocks → AgentError."""
        # Build a response with stop_reason=tool_use but no tool_use blocks.
        resp = make_text_response("I'll do something...", stop_reason="tool_use")
        bench["llm"].responses = [resp]
        events = await collect_events(bench["agent"], "do it")

        errors = [e for e in events if isinstance(e, AgentError) and not e.recoverable]
        assert len(errors) >= 1
        assert "no tool_use blocks" in errors[0].message.lower()


class TestMessageHistory:
    """Additional tests for message history management."""

    async def test_messages_property_returns_copy(self, bench) -> None:
        """agent.messages returns a copy, not the internal list."""
        bench["llm"].responses = [make_text_response("Hi")]
        await collect_events(bench["agent"], "hello")

        msgs = bench["agent"].messages
        msgs.append({"role": "user", "content": "extra"})

        # The internal list is unchanged.
        assert len(bench["agent"].messages) != len(msgs)

    async def test_assistant_text_persisted_in_history(self, bench) -> None:
        """After a text response, the assistant turn is in the message history."""
        bench["llm"].responses = [make_text_response("Hello back!")]
        await collect_events(bench["agent"], "hello")

        msgs = bench["agent"].messages
        # Should have user + assistant.
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"][0]["text"] == "Hello back!"
