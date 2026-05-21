"""Full agent loop driving real tools against `tmp_path`.

These exercise the seam where the loop wires the registry's tools to the
provider's tool calls and feeds their results back. No mocked filesystem —
`Read`, `Write`, and `Bash` run real I/O against pytest's `tmp_path`.
"""

import json
from pathlib import Path

from termcoder.agent.loop import Agent
from termcoder.events import TextDelta, ToolCallCompleted, ToolCallRequested, TurnComplete
from termcoder.models import ToolCall
from termcoder.tools.bash import Bash
from termcoder.tools.edit import Edit
from termcoder.tools.read import Read
from termcoder.tools.registry import Registry
from termcoder.tools.write import Write
from tests.fakes.fake_permission import FakePermission
from tests.fakes.fake_provider import FakeProvider


def _tool_call(name: str, id_: str, args: dict[str, object]) -> ToolCall:
    return ToolCall(id=id_, name=name, arguments=json.dumps(args))


async def test_write_then_read_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    write_call = _tool_call("write", "w1", {"path": str(target), "content": "hello"})
    read_call = _tool_call("read", "r1", {"path": str(target)})

    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=write_call)],
            [ToolCallRequested(tool_call=read_call)],
            [TextDelta(text="file says: hello")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([Read(), Write()]),
        check_permission=FakePermission(),
    )

    events = [e async for e in agent.run_turn("write hello to note.txt then read it back")]
    completed = [e for e in events if isinstance(e, ToolCallCompleted)]

    assert target.read_text() == "hello"
    assert [r.result.is_error for r in completed] == [False, False]
    assert completed[1].result.content == "hello"
    assert events[-1] == TurnComplete()


async def test_read_missing_file_surfaces_error_back_to_model(tmp_path: Path) -> None:
    missing = tmp_path / "nope.txt"
    read_call = _tool_call("read", "r1", {"path": str(missing)})
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=read_call)],
            [TextDelta(text="file doesn't exist")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([Read()]),
        check_permission=FakePermission(),
    )

    events = [e async for e in agent.run_turn("read it")]
    completed = next(e for e in events if isinstance(e, ToolCallCompleted))

    # Tool failure surfaces as is_error=True in the ToolResult — the loop does not raise.
    assert completed.result.is_error is True
    # And the model sees the error text in the second provider call's tool message.
    _, _ = provider.received_calls[1]
    second_messages = provider.received_calls[1][0]
    tool_message = second_messages[-1]
    assert tool_message.role == "tool"
    assert "read failed" in tool_message.content


async def test_bash_command_output_feeds_back_to_provider(tmp_path: Path) -> None:
    bash_call = _tool_call("bash", "b1", {"command": "echo hello-from-shell"})
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=bash_call)],
            [TextDelta(text="got it")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([Bash()]),
        check_permission=FakePermission(),
    )

    [_ async for _ in agent.run_turn("run echo")]

    second_messages = provider.received_calls[1][0]
    tool_message = second_messages[-1]
    assert tool_message.role == "tool"
    assert "hello-from-shell" in tool_message.content


async def test_edit_result_feeds_back_to_provider(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("hello old world", encoding="utf-8")
    edit_call = _tool_call(
        "edit",
        "e1",
        {"path": str(target), "old": "old", "new": "new"},
    )
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=edit_call)],
            [TextDelta(text="updated")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([Edit()]),
        check_permission=FakePermission(),
    )

    [_ async for _ in agent.run_turn("replace old with new")]

    assert target.read_text(encoding="utf-8") == "hello new world"
    tool_message = provider.received_calls[1][0][-1]
    assert tool_message.role == "tool"
    assert "replaced 1 occurrence" in tool_message.content


async def test_denial_passes_a_denial_message_to_the_next_round(tmp_path: Path) -> None:
    target = tmp_path / "danger.txt"
    write_call = _tool_call("write", "w1", {"path": str(target), "content": "x"})
    provider = FakeProvider(
        scripts=[
            [ToolCallRequested(tool_call=write_call)],
            [TextDelta(text="understood, will not write")],
        ]
    )
    agent = Agent(
        provider=provider,
        registry=Registry([Write()]),
        check_permission=FakePermission(default="deny"),
    )

    [_ async for _ in agent.run_turn("write please")]

    assert not target.exists()  # write tool never ran
    tool_message = provider.received_calls[1][0][-1]
    assert tool_message.role == "tool"
    assert "denied" in tool_message.content.lower()
