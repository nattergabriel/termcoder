"""Tests for the Anthropic Messages API provider.

Three pieces in isolation, matching the OpenAI-compatible provider's structure:
the raw-event translator, the message/tool wire converters, and the thin glue
around `AsyncAnthropic.messages.create`. The translator is exercised against
hand-built `Raw*` event objects; the glue uses a structural fake of the client.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import cast

from anthropic import AsyncAnthropic, omit
from anthropic.types import (
    InputJSONDelta,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageStreamEvent,
    ToolUseBlock,
)
from anthropic.types import (
    TextDelta as AnthropicTextDelta,
)

from termcoder.events import TextDelta, ToolCallRequested
from termcoder.models import Message, ToolCall, ToolSchema
from termcoder.providers.anthropic import (
    AnthropicProvider,
    _split_system_and_convert,
    _to_api_tool,
    _translate,
)

# --- translation tests --------------------------------------------------------


async def test_translates_text_deltas_in_order() -> None:
    chunks: list[RawMessageStreamEvent] = [
        _text_delta("Hel"),
        _text_delta("lo"),
        _text_delta("!"),
    ]

    events = [e async for e in _translate(_aiter(chunks))]

    assert events == [TextDelta(text="Hel"), TextDelta(text="lo"), TextDelta(text="!")]


async def test_accumulates_tool_call_arguments_across_deltas() -> None:
    chunks: list[RawMessageStreamEvent] = [
        _tool_start(index=0, id_="call_1", name="read"),
        _input_json_delta(index=0, partial='{"pa'),
        _input_json_delta(index=0, partial='th": "x"}'),
        _block_stop(index=0),
    ]

    events = [e async for e in _translate(_aiter(chunks))]

    assert events == [
        ToolCallRequested(tool_call=ToolCall(id="call_1", name="read", arguments='{"path": "x"}'))
    ]


async def test_emits_tool_calls_in_stop_order() -> None:
    chunks: list[RawMessageStreamEvent] = [
        _tool_start(index=0, id_="call_a", name="read"),
        _input_json_delta(index=0, partial="{}"),
        _block_stop(index=0),
        _tool_start(index=1, id_="call_b", name="write"),
        _input_json_delta(index=1, partial="{}"),
        _block_stop(index=1),
    ]

    events = [e async for e in _translate(_aiter(chunks))]

    assert events == [
        ToolCallRequested(tool_call=ToolCall(id="call_a", name="read", arguments="{}")),
        ToolCallRequested(tool_call=ToolCall(id="call_b", name="write", arguments="{}")),
    ]


async def test_interleaves_text_then_emits_tool_call_at_stop() -> None:
    chunks: list[RawMessageStreamEvent] = [
        _text_delta("Looking..."),
        _tool_start(index=1, id_="c1", name="read"),
        _input_json_delta(index=1, partial='{"path": "f"}'),
        _block_stop(index=1),
    ]

    events = [e async for e in _translate(_aiter(chunks))]

    assert events == [
        TextDelta(text="Looking..."),
        ToolCallRequested(tool_call=ToolCall(id="c1", name="read", arguments='{"path": "f"}')),
    ]


async def test_ignores_text_block_stop() -> None:
    chunks: list[RawMessageStreamEvent] = [_text_delta("hi"), _block_stop(index=0)]

    events = [e async for e in _translate(_aiter(chunks))]

    assert events == [TextDelta(text="hi")]


# --- message conversion tests -------------------------------------------------


def test_extracts_leading_system_message() -> None:
    system, msgs = _split_system_and_convert(
        [
            Message(role="system", content="be helpful"),
            Message(role="user", content="hi"),
        ]
    )

    assert system == "be helpful"
    assert msgs == [{"role": "user", "content": "hi"}]


def test_joins_multiple_system_messages_with_blank_line() -> None:
    system, _ = _split_system_and_convert(
        [
            Message(role="system", content="be helpful"),
            Message(role="system", content="be terse"),
            Message(role="user", content="hi"),
        ]
    )

    assert system == "be helpful\n\nbe terse"


def test_converts_assistant_text_message() -> None:
    _, msgs = _split_system_and_convert([Message(role="assistant", content="sure")])

    assert msgs == [{"role": "assistant", "content": [{"type": "text", "text": "sure"}]}]


def test_converts_assistant_message_with_tool_calls() -> None:
    msg = Message(
        role="assistant",
        content="thinking",
        tool_calls=(ToolCall(id="call_1", name="read", arguments='{"path": "x"}'),),
    )

    _, msgs = _split_system_and_convert([msg])

    assert msgs == [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "thinking"},
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "read",
                    "input": {"path": "x"},
                },
            ],
        }
    ]


def test_assistant_with_tool_calls_only_omits_empty_text_block() -> None:
    msg = Message(
        role="assistant",
        content="",
        tool_calls=(ToolCall(id="c1", name="read", arguments="{}"),),
    )

    _, msgs = _split_system_and_convert([msg])

    assert msgs == [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "c1", "name": "read", "input": {}},
            ],
        }
    ]


def test_collapses_adjacent_tool_messages_into_one_user_turn() -> None:
    msgs_in = [
        Message(role="user", content="run tools"),
        Message(
            role="assistant",
            content="",
            tool_calls=(
                ToolCall(id="c1", name="read", arguments="{}"),
                ToolCall(id="c2", name="write", arguments="{}"),
            ),
        ),
        Message(role="tool", content="file body", tool_call_id="c1"),
        Message(role="tool", content="ok", tool_call_id="c2"),
        Message(role="user", content="thanks"),
    ]

    _, msgs = _split_system_and_convert(msgs_in)

    assert msgs == [
        {"role": "user", "content": "run tools"},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "c1", "name": "read", "input": {}},
                {"type": "tool_use", "id": "c2", "name": "write", "input": {}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "c1", "content": "file body"},
                {"type": "tool_result", "tool_use_id": "c2", "content": "ok"},
            ],
        },
        {"role": "user", "content": "thanks"},
    ]


# --- tool schema conversion ---------------------------------------------------


def test_converts_tool_schema() -> None:
    schema = ToolSchema(
        name="read",
        description="read a file",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
    )

    assert _to_api_tool(schema) == {
        "name": "read",
        "description": "read a file",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
    }


# --- end-to-end provider with a fake AsyncAnthropic ---------------------------


async def test_provider_forwards_messages_and_tools_then_yields_translated_events() -> None:
    client = _FakeClient(
        [
            _text_delta("ok"),
            _tool_start(index=1, id_="c1", name="read"),
            _input_json_delta(index=1, partial='{"path": "/a"}'),
            _block_stop(index=1),
        ]
    )
    provider = AnthropicProvider(
        client=cast(AsyncAnthropic, client), model="claude-x", temperature=0.7
    )
    msg = Message(role="user", content="open /a")
    schema = ToolSchema(name="read", description="read", parameters={"type": "object"})

    events = [e async for e in provider.stream([msg], [schema])]

    assert events == [
        TextDelta(text="ok"),
        ToolCallRequested(tool_call=ToolCall(id="c1", name="read", arguments='{"path": "/a"}')),
    ]
    kwargs = client.messages.last_kwargs
    assert kwargs["model"] == "claude-x"
    assert kwargs["stream"] is True
    assert kwargs["temperature"] == 0.7
    # AnthropicProvider supplies its own default when max_tokens is left unset.
    assert isinstance(kwargs["max_tokens"], int)
    assert kwargs["max_tokens"] > 0
    assert kwargs["messages"] == [{"role": "user", "content": "open /a"}]
    assert kwargs["system"] is omit
    assert kwargs["tools"] == [
        {
            "name": "read",
            "description": "read",
            "input_schema": {"type": "object"},
        }
    ]


async def test_provider_pulls_system_message_into_top_level_kwarg() -> None:
    client = _FakeClient([_text_delta("hi")])
    provider = AnthropicProvider(client=cast(AsyncAnthropic, client), model="m", temperature=0.7)

    [_ async for _ in provider.stream([Message(role="system", content="be terse")], [])]

    kwargs = client.messages.last_kwargs
    assert kwargs["system"] == "be terse"
    assert kwargs["messages"] == []


async def test_provider_passes_not_given_for_tools_when_none_provided() -> None:
    client = _FakeClient([_text_delta("hi")])
    provider = AnthropicProvider(client=cast(AsyncAnthropic, client), model="m", temperature=0.7)

    [_ async for _ in provider.stream([], [])]

    assert client.messages.last_kwargs["tools"] is omit


async def test_provider_forwards_generation_settings() -> None:
    client = _FakeClient([_text_delta("hi")])
    provider = AnthropicProvider(
        client=cast(AsyncAnthropic, client),
        model="m",
        temperature=0.2,
        max_tokens=123,
    )

    [_ async for _ in provider.stream([], [])]

    kwargs = client.messages.last_kwargs
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 123


# --- helpers ------------------------------------------------------------------


def _text_delta(text: str) -> RawContentBlockDeltaEvent:
    return RawContentBlockDeltaEvent(
        type="content_block_delta",
        index=0,
        delta=AnthropicTextDelta(type="text_delta", text=text),
    )


def _tool_start(*, index: int, id_: str, name: str) -> RawContentBlockStartEvent:
    return RawContentBlockStartEvent(
        type="content_block_start",
        index=index,
        content_block=ToolUseBlock(type="tool_use", id=id_, name=name, input={}),
    )


def _input_json_delta(*, index: int, partial: str) -> RawContentBlockDeltaEvent:
    return RawContentBlockDeltaEvent(
        type="content_block_delta",
        index=index,
        delta=InputJSONDelta(type="input_json_delta", partial_json=partial),
    )


def _block_stop(*, index: int) -> RawContentBlockStopEvent:
    return RawContentBlockStopEvent(type="content_block_stop", index=index)


async def _aiter(items: Sequence[RawMessageStreamEvent]) -> AsyncIterator[RawMessageStreamEvent]:
    for item in items:
        yield item


@dataclass
class _FakeMessages:
    chunks: list[RawMessageStreamEvent]
    last_kwargs: dict[str, object] = field(default_factory=dict)

    async def create(self, **kwargs: object) -> AsyncIterator[RawMessageStreamEvent]:
        self.last_kwargs = kwargs
        return _aiter(self.chunks)


class _FakeClient:
    """Duck-typed `AsyncAnthropic` providing only `.messages.create`."""

    def __init__(self, chunks: list[RawMessageStreamEvent]) -> None:
        self.messages = _FakeMessages(chunks=chunks)
