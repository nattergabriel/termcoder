"""Tests for the OpenAI-compatible provider.

The provider has three pieces worth testing in isolation: the chunk-stream
translator, the message/tool wire converters, and the thin glue around the
SDK's `chat.completions.create`. The first two are tested as pure functions
against hand-built `ChatCompletionChunk` objects; the glue is exercised via
a structural fake of `AsyncOpenAI` so no network is touched.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import cast

from openai import AsyncOpenAI, omit
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import (
    Choice,
    ChoiceDelta,
    ChoiceDeltaToolCall,
    ChoiceDeltaToolCallFunction,
)

from termcoder.events import TextDelta, ToolCallRequested
from termcoder.models import Message, ToolCall, ToolSchema
from termcoder.providers.openai_compatible import (
    OpenAICompatibleProvider,
    _to_api_message,
    _to_api_tool,
    _translate,
)

# --- translation tests --------------------------------------------------------


async def test_translates_text_deltas_in_order() -> None:
    chunks = [_text_chunk("Hel"), _text_chunk("lo"), _text_chunk("!")]

    events = [e async for e in _translate(_aiter(chunks))]

    assert events == [TextDelta(text="Hel"), TextDelta(text="lo"), TextDelta(text="!")]


async def test_accumulates_tool_call_arguments_across_chunks() -> None:
    chunks = [
        _tool_chunk(index=0, id_="call_1", name="read", arguments='{"pa'),
        _tool_chunk(index=0, arguments='th": "x"}'),
    ]

    events = [e async for e in _translate(_aiter(chunks))]

    assert events == [
        ToolCallRequested(tool_call=ToolCall(id="call_1", name="read", arguments='{"path": "x"}'))
    ]


async def test_emits_multiple_tool_calls_in_index_order() -> None:
    chunks = [
        _tool_chunk(index=1, id_="call_b", name="write", arguments="{}"),
        _tool_chunk(index=0, id_="call_a", name="read", arguments="{}"),
    ]

    events = [e async for e in _translate(_aiter(chunks))]

    assert events == [
        ToolCallRequested(tool_call=ToolCall(id="call_a", name="read", arguments="{}")),
        ToolCallRequested(tool_call=ToolCall(id="call_b", name="write", arguments="{}")),
    ]


async def test_interleaves_text_then_emits_tool_call_at_end() -> None:
    chunks = [
        _text_chunk("Looking..."),
        _tool_chunk(index=0, id_="c1", name="read", arguments='{"path": "f"}'),
    ]

    events = [e async for e in _translate(_aiter(chunks))]

    assert events == [
        TextDelta(text="Looking..."),
        ToolCallRequested(tool_call=ToolCall(id="c1", name="read", arguments='{"path": "f"}')),
    ]


async def test_skips_chunks_without_choices() -> None:
    # Some OpenAI-compatible endpoints (e.g. Azure) lead with a metadata-only chunk.
    metadata_only = ChatCompletionChunk(
        id="x", object="chat.completion.chunk", created=0, model="m", choices=[]
    )

    events = [e async for e in _translate(_aiter([metadata_only, _text_chunk("hi")]))]

    assert events == [TextDelta(text="hi")]


# --- message conversion tests -------------------------------------------------


def test_converts_system_message() -> None:
    assert _to_api_message(Message(role="system", content="be helpful")) == {
        "role": "system",
        "content": "be helpful",
    }


def test_converts_user_message() -> None:
    assert _to_api_message(Message(role="user", content="hi")) == {
        "role": "user",
        "content": "hi",
    }


def test_converts_assistant_text_message() -> None:
    assert _to_api_message(Message(role="assistant", content="sure")) == {
        "role": "assistant",
        "content": "sure",
    }


def test_converts_assistant_message_with_tool_calls() -> None:
    msg = Message(
        role="assistant",
        content="",
        tool_calls=(ToolCall(id="call_1", name="read", arguments='{"path": "x"}'),),
    )

    assert _to_api_message(msg) == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "read", "arguments": '{"path": "x"}'},
            }
        ],
    }


def test_converts_tool_result_message() -> None:
    msg = Message(role="tool", content="file contents", tool_call_id="call_1")

    assert _to_api_message(msg) == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "file contents",
    }


# --- tool schema conversion ---------------------------------------------------


def test_converts_tool_schema() -> None:
    schema = ToolSchema(
        name="read",
        description="read a file",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
    )

    assert _to_api_tool(schema) == {
        "type": "function",
        "function": {
            "name": "read",
            "description": "read a file",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
        },
    }


# --- end-to-end provider with a fake AsyncOpenAI ------------------------------


async def test_provider_forwards_messages_and_tools_then_yields_translated_events() -> None:
    client = _FakeClient(
        [
            _text_chunk("ok"),
            _tool_chunk(index=0, id_="c1", name="read", arguments='{"path": "/a"}'),
        ]
    )
    provider = OpenAICompatibleProvider(
        client=cast(AsyncOpenAI, client), model="gpt-4o-mini", temperature=0.7
    )
    msg = Message(role="user", content="open /a")
    schema = ToolSchema(name="read", description="read", parameters={"type": "object"})

    events = [e async for e in provider.stream([msg], [schema])]

    assert events == [
        TextDelta(text="ok"),
        ToolCallRequested(tool_call=ToolCall(id="c1", name="read", arguments='{"path": "/a"}')),
    ]
    kwargs = client.chat.completions.last_kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["stream"] is True
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] is omit
    assert kwargs["messages"] == [{"role": "user", "content": "open /a"}]
    assert kwargs["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "read",
                "description": "read",
                "parameters": {"type": "object"},
            },
        }
    ]


async def test_provider_passes_omit_sentinel_for_tools_when_none_provided() -> None:
    # The SDK drops `omit` kwargs from the wire request — we just need to forward
    # the sentinel rather than a real list, so it doesn't get sent as `tools: []`.
    client = _FakeClient([_text_chunk("hi")])
    provider = OpenAICompatibleProvider(
        client=cast(AsyncOpenAI, client), model="m", temperature=0.7
    )

    [_ async for _ in provider.stream([], [])]

    assert client.chat.completions.last_kwargs["tools"] is omit


async def test_provider_forwards_generation_settings() -> None:
    client = _FakeClient([_text_chunk("hi")])
    provider = OpenAICompatibleProvider(
        client=cast(AsyncOpenAI, client),
        model="m",
        temperature=0.2,
        max_tokens=123,
    )

    [_ async for _ in provider.stream([], [])]

    kwargs = client.chat.completions.last_kwargs
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 123


# --- helpers ------------------------------------------------------------------


def _text_chunk(text: str) -> ChatCompletionChunk:
    return ChatCompletionChunk(
        id="x",
        object="chat.completion.chunk",
        created=0,
        model="m",
        choices=[Choice(index=0, delta=ChoiceDelta(content=text), finish_reason=None)],
    )


def _tool_chunk(
    *,
    index: int,
    id_: str | None = None,
    name: str | None = None,
    arguments: str = "",
) -> ChatCompletionChunk:
    function = ChoiceDeltaToolCallFunction(name=name, arguments=arguments)
    return ChatCompletionChunk(
        id="x",
        object="chat.completion.chunk",
        created=0,
        model="m",
        choices=[
            Choice(
                index=0,
                delta=ChoiceDelta(
                    tool_calls=[
                        ChoiceDeltaToolCall(index=index, id=id_, type="function", function=function)
                    ]
                ),
                finish_reason=None,
            )
        ],
    )


async def _aiter(items: Sequence[ChatCompletionChunk]) -> AsyncIterator[ChatCompletionChunk]:
    for item in items:
        yield item


@dataclass
class _FakeCompletions:
    chunks: list[ChatCompletionChunk]
    last_kwargs: dict[str, object] = field(default_factory=dict)

    async def create(self, **kwargs: object) -> AsyncIterator[ChatCompletionChunk]:
        self.last_kwargs = kwargs
        return _aiter(self.chunks)


@dataclass
class _FakeChat:
    completions: _FakeCompletions


class _FakeClient:
    """Duck-typed `AsyncOpenAI` providing only `.chat.completions.create`."""

    def __init__(self, chunks: list[ChatCompletionChunk]) -> None:
        self.chat = _FakeChat(completions=_FakeCompletions(chunks=chunks))
