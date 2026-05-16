"""Smoke tests for the scripted FakeProvider.

The fake is itself a test double, but it has enough logic (script consumption,
call recording, exhaustion guard) to warrant a small confidence check before
the agent loop tests in step 5 start depending on it.
"""

import pytest

from termcoder.events import TextDelta, TurnComplete
from termcoder.types import Message, ToolSchema
from tests.fakes.fake_provider import FakeProvider


async def test_yields_scripted_events_in_order() -> None:
    fake = FakeProvider(scripts=[[TextDelta(text="hi"), TurnComplete()]])

    events = [event async for event in fake.stream([], [])]

    assert events == [TextDelta(text="hi"), TurnComplete()]


async def test_records_messages_and_tools_eagerly() -> None:
    fake = FakeProvider(scripts=[[]])
    msg = Message(role="user", content="hello")
    schema = ToolSchema(name="read", description="read a file", parameters={"type": "object"})

    iterator = fake.stream([msg], [schema])

    assert fake.received_calls == [((msg,), (schema,))]
    [_ async for _ in iterator]  # drain to avoid unawaited-coroutine warning


async def test_each_call_consumes_next_script() -> None:
    fake = FakeProvider(scripts=[[TextDelta(text="first")], [TextDelta(text="second")]])

    first = [event async for event in fake.stream([], [])]
    second = [event async for event in fake.stream([], [])]

    assert first == [TextDelta(text="first")]
    assert second == [TextDelta(text="second")]


async def test_raises_when_scripts_exhausted() -> None:
    fake = FakeProvider(scripts=[])

    with pytest.raises(RuntimeError, match="no more scripts"):
        fake.stream([], [])
