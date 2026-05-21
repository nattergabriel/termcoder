"""Unit tests for the agent loop.

Drives `Agent.run_turn` against a `FakeProvider` and a `FakeTool` so we can
script multi-round conversations deterministically without any real I/O.
The mid-stream gating test uses an `asyncio.Event` to prove the loop actually
awaits the permission callable before dispatching a tool.
"""

import asyncio
from collections.abc import AsyncIterator, Sequence

import pytest

from termcoder.agent.loop import Agent
from termcoder.errors import TermcoderError
from termcoder.events import (
    AgentEvent,
    TextDelta,
    ToolCallCompleted,
    ToolCallRequested,
    ToolCallStarted,
    TurnComplete,
)
from termcoder.models import Message, PermissionDecision, ToolCall, ToolResult, ToolSchema
from termcoder.tools.registry import Registry
from tests.fakes.fake_permission import FakePermission
from tests.fakes.fake_provider import FakeProvider
from tests.fakes.fake_tool import FakeTool


async def test_text_only_turn_yields_deltas_then_turn_complete() -> None:
    provider = FakeProvider(scripts=[[TextDelta(text="hel"), TextDelta(text="lo")]])
    agent = Agent(
        provider=provider,
        registry=Registry(),
        check_permission=FakePermission(),
        system_prompt="",
    )

    events = [e async for e in agent.run_turn("hi")]

    assert events == [TextDelta(text="hel"), TextDelta(text="lo"), TurnComplete()]
    assert agent.state.messages == (
        Message(role="user", content="hi"),
        Message(role="assistant", content="hello"),
    )


async def test_runs_tool_then_continues_with_result_in_next_round() -> None:
    tool = FakeTool(
        name="read",
        scripted_results=[ToolResult(tool_call_id="", content="FILE_BODY")],
    )
    call = ToolCall(id="c1", name="read", arguments='{"path": "x"}')
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=call)],
            [TextDelta(text="done")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([tool]),
        check_permission=FakePermission(),
        system_prompt="",
    )

    events = [e async for e in agent.run_turn("read x")]

    assert events == [
        ToolCallRequested(tool_call=call),
        ToolCallStarted(tool_call=call),
        ToolCallCompleted(result=ToolResult(tool_call_id="c1", content="FILE_BODY")),
        TextDelta(text="done"),
        TurnComplete(),
    ]
    assert tool.received == [call]
    assert agent.state.messages == (
        Message(role="user", content="read x"),
        Message(role="assistant", content="", tool_calls=(call,)),
        Message(role="tool", content="FILE_BODY", tool_call_id="c1"),
        Message(role="assistant", content="done"),
    )


async def test_second_provider_call_includes_tool_result_message() -> None:
    tool = FakeTool(name="read", scripted_results=[ToolResult(tool_call_id="", content="BODY")])
    call = ToolCall(id="c1", name="read", arguments="{}")
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=call)],
            [TextDelta(text="ok")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([tool]),
        check_permission=FakePermission(),
        system_prompt="",
    )

    [_ async for _ in agent.run_turn("go")]

    # First call: just the user message. Second call: user + assistant(tool_call) + tool result.
    first_messages, _ = provider.received_calls[0]
    second_messages, _ = provider.received_calls[1]
    assert first_messages == (Message(role="user", content="go"),)
    assert second_messages == (
        Message(role="user", content="go"),
        Message(role="assistant", content="", tool_calls=(call,)),
        Message(role="tool", content="BODY", tool_call_id="c1"),
    )


async def test_denied_tool_call_returns_error_result_without_invoking_tool() -> None:
    tool = FakeTool(name="bash")
    call = ToolCall(id="c1", name="bash", arguments='{"cmd": "rm -rf /"}')
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=call)],
            [TextDelta(text="ok, skipping")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([tool]),
        check_permission=FakePermission(default="deny"),
        system_prompt="",
    )

    events = [e async for e in agent.run_turn("be dangerous")]

    completed = [e for e in events if isinstance(e, ToolCallCompleted)]
    started = [e for e in events if isinstance(e, ToolCallStarted)]
    assert len(completed) == 1
    assert started == []
    assert completed[0].result.is_error is True
    assert "denied" in completed[0].result.content.lower()
    assert tool.received == []  # tool was never invoked


async def test_unknown_tool_returns_error_result() -> None:
    call = ToolCall(id="c1", name="missing", arguments="{}")
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=call)],
            [TextDelta(text="that tool doesn't exist")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry(),
        check_permission=FakePermission(),
        system_prompt="",
    )

    events = [e async for e in agent.run_turn("call missing")]

    completed = [e for e in events if isinstance(e, ToolCallCompleted)]
    started = [e for e in events if isinstance(e, ToolCallStarted)]
    assert started == []
    assert completed[0].result.is_error is True
    assert "missing" in completed[0].result.content


async def test_multiple_tool_calls_in_one_round_run_in_order() -> None:
    read_tool = FakeTool(name="read", scripted_results=[ToolResult(tool_call_id="", content="R")])
    bash_tool = FakeTool(name="bash", scripted_results=[ToolResult(tool_call_id="", content="B")])
    call_a = ToolCall(id="a", name="read", arguments="{}")
    call_b = ToolCall(id="b", name="bash", arguments="{}")
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=call_a), ToolCallRequested(tool_call=call_b)],
            [TextDelta(text="all done")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([read_tool, bash_tool]),
        check_permission=FakePermission(),
        system_prompt="",
    )

    events = [e async for e in agent.run_turn("do two things")]
    started_calls = [e.tool_call.id for e in events if isinstance(e, ToolCallStarted)]
    completed_results = [e.result for e in events if isinstance(e, ToolCallCompleted)]

    assert started_calls == ["a", "b"]
    assert [r.tool_call_id for r in completed_results] == ["a", "b"]
    assert [r.content for r in completed_results] == ["R", "B"]


async def test_system_prompt_is_prepended_to_provider_messages() -> None:
    provider = FakeProvider(scripts=[[TextDelta(text="hi")]])
    agent = Agent(
        provider=provider,
        registry=Registry(),
        check_permission=FakePermission(),
        system_prompt="be terse",
    )

    [_ async for _ in agent.run_turn("hello")]

    sent_messages, _ = provider.received_calls[0]
    assert sent_messages[0] == Message(role="system", content="be terse")
    assert sent_messages[1] == Message(role="user", content="hello")
    # System prompt is composition-level config, not part of `State`.
    assert all(m.role != "system" for m in agent.state.messages)


async def test_loop_blocks_on_permission_callable_before_dispatching_tool() -> None:
    """Mid-stream gating: tool call is yielded, then the loop awaits permission
    before the tool runs and before `ToolCallCompleted` is yielded."""
    gate = asyncio.Event()
    permission_entered = asyncio.Event()
    tool_ran = asyncio.Event()

    async def gated_permission(_: ToolCall) -> PermissionDecision:
        permission_entered.set()
        await gate.wait()
        return "allow"

    class GatedTool:
        name = "slow"
        schema = FakeTool(name="slow").schema

        async def run(self, call: ToolCall) -> ToolResult:
            tool_ran.set()
            return ToolResult(tool_call_id=call.id, content="ran")

    call = ToolCall(id="c1", name="slow", arguments="{}")
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=call)],
            [TextDelta(text="finished")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([GatedTool()]),
        check_permission=gated_permission,
        system_prompt="",
    )

    gen = agent.run_turn("go")
    first_event = await gen.__anext__()
    assert first_event == ToolCallRequested(tool_call=call)

    # The next event requires the permission gate. Wait until the loop has
    # actually entered the permission callable (proves it's blocked *on the gate*,
    # not somewhere else), and confirm the tool has not yet been invoked.
    pending = asyncio.ensure_future(gen.__anext__())
    await asyncio.wait_for(permission_entered.wait(), timeout=1.0)
    assert not pending.done()
    assert not tool_ran.is_set()

    gate.set()
    started = await pending
    assert started == ToolCallStarted(tool_call=call)
    assert not tool_ran.is_set()

    next_event = await gen.__anext__()
    assert isinstance(next_event, ToolCallCompleted)
    assert tool_ran.is_set()

    remaining = [e async for e in gen]
    assert remaining == [TextDelta(text="finished"), TurnComplete()]


async def test_cancelled_turn_rolls_back_partial_state() -> None:
    gate = asyncio.Event()
    permission_entered = asyncio.Event()

    async def gated_permission(_: ToolCall) -> PermissionDecision:
        permission_entered.set()
        await gate.wait()
        return "allow"

    call = ToolCall(id="c1", name="read", arguments="{}")
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=call)],
            [TextDelta(text="finished")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([FakeTool(name="read")]),
        check_permission=gated_permission,
        system_prompt="",
    )

    gen = agent.run_turn("go")
    first_event = await gen.__anext__()
    assert first_event == ToolCallRequested(tool_call=call)

    pending: asyncio.Future[AgentEvent] = asyncio.ensure_future(gen.__anext__())
    await asyncio.wait_for(permission_entered.wait(), timeout=1.0)
    assert agent.state.messages == (
        Message(role="user", content="go"),
        Message(role="assistant", content="", tool_calls=(call,)),
    )

    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending

    assert len(agent.state.messages) == 0


async def test_raises_when_max_iterations_exceeded() -> None:
    """A model that keeps requesting tool calls without ever finishing hits the cap."""
    tool = FakeTool(name="loop")
    call = ToolCall(id="c", name="loop", arguments="{}")
    # Two scripts of tool calls; with max_iterations=2 the third round would raise.
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=call)],
            [ToolCallRequested(tool_call=call)],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([tool]),
        check_permission=FakePermission(),
        system_prompt="",
        max_iterations=2,
    )

    with pytest.raises(TermcoderError, match="max_iterations=2"):
        async for _ in agent.run_turn("loop forever"):
            pass


async def test_provider_error_mid_stream_rolls_back_partial_state() -> None:
    """A provider that raises mid-turn must not leave a dangling user message."""

    class ExplodingProvider:
        model = "boom"
        temperature = 0.7

        async def stream(
            self,
            messages: Sequence[Message],
            tools: Sequence[ToolSchema],
        ) -> AsyncIterator[AgentEvent]:
            yield TextDelta(text="partial ")
            raise RuntimeError("network died")

    agent = Agent(
        provider=ExplodingProvider(),
        registry=Registry(),
        check_permission=FakePermission(),
        system_prompt="",
    )

    with pytest.raises(RuntimeError, match="network died"):
        async for _ in agent.run_turn("ask something"):
            pass

    assert agent.state.messages == ()
