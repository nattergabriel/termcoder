"""Unit tests for the conversation `State`.

State is a thin append-only log; these tests just lock in the message shapes
each appender produces and that order is preserved.
"""

from termcoder.agent.state import State
from termcoder.types import Message, ToolCall, ToolResult


def test_starts_empty() -> None:
    assert State().messages == ()


def test_appends_each_role_with_correct_shape() -> None:
    state = State()

    state.append_user("hi")
    state.append_assistant(
        "thinking...",
        [ToolCall(id="c1", name="read", arguments='{"path": "x"}')],
    )
    state.append_tool_result(ToolResult(tool_call_id="c1", content="file body"))

    assert state.messages == (
        Message(role="user", content="hi"),
        Message(
            role="assistant",
            content="thinking...",
            tool_calls=(ToolCall(id="c1", name="read", arguments='{"path": "x"}'),),
        ),
        Message(role="tool", content="file body", tool_call_id="c1"),
    )


def test_assistant_message_with_no_tool_calls_has_empty_tuple() -> None:
    state = State()
    state.append_assistant("just text")
    assert state.messages[0].tool_calls == ()


def test_messages_returns_immutable_snapshot() -> None:
    state = State()
    state.append_user("hi")

    snapshot = state.messages
    state.append_user("there")

    # The snapshot taken before the second append must not reflect it.
    assert snapshot == (Message(role="user", content="hi"),)
    assert len(state.messages) == 2


def test_truncates_to_checkpoint() -> None:
    state = State()
    state.append_user("kept")
    checkpoint = len(state.messages)
    state.append_user("dropped")
    state.append_assistant("also dropped")

    state.truncate(checkpoint)

    assert state.messages == (Message(role="user", content="kept"),)
