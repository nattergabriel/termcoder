"""Unit tests for the conversation `State`."""

from termcoder.agent.state import State
from termcoder.models import Message


def test_starts_empty() -> None:
    assert State().messages == ()


def test_appends_messages_in_order() -> None:
    state = State()
    user_message = Message(role="user", content="hi")
    assistant_message = Message(role="assistant", content="hello")

    state.append(user_message)
    state.append(assistant_message)

    assert state.messages == (user_message, assistant_message)


def test_messages_returns_immutable_snapshot() -> None:
    state = State()
    state.append(Message(role="user", content="hi"))

    snapshot = state.messages
    state.append(Message(role="user", content="there"))

    # The snapshot taken before the second append must not reflect it.
    assert snapshot == (Message(role="user", content="hi"),)
    assert len(state.messages) == 2


def test_truncates_to_checkpoint() -> None:
    state = State()
    state.append(Message(role="user", content="kept"))
    checkpoint = len(state.messages)
    state.append(Message(role="user", content="dropped"))
    state.append(Message(role="assistant", content="also dropped"))

    state.truncate(checkpoint)

    assert state.messages == (Message(role="user", content="kept"),)
