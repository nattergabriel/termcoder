"""Anthropic Messages API streaming provider.

Translates between our `Message` / `ToolSchema` / `AgentEvent` types and the
Anthropic SDK's wire shapes. Every `anthropic.*` import stays inside this
module; the agent core never sees vendor types.
"""

import json
from collections.abc import AsyncIterable, AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, assert_never

from anthropic import NOT_GIVEN, AsyncAnthropic, NotGiven
from anthropic.types import RawMessageStreamEvent

from termcoder.events import AgentEvent, TextDelta, ToolCallRequested
from termcoder.types import Message, ToolCall, ToolSchema

# Anthropic requires `max_tokens`; this is the fallback when Config leaves it unset.
DEFAULT_MAX_TOKENS = 4096


@dataclass
class AnthropicProvider:
    """Streams `AgentEvent`s from the Anthropic Messages API."""

    client: AsyncAnthropic
    model: str
    temperature: float = 0.7
    max_tokens: int = DEFAULT_MAX_TOKENS

    async def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSchema],
    ) -> AsyncIterator[AgentEvent]:
        system, api_messages = _to_api_messages(messages)
        api_tools: list[Any] | NotGiven = [_to_api_tool(t) for t in tools] if tools else NOT_GIVEN
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "tools": api_tools,
            "stream": True,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system": system if system else NOT_GIVEN,
        }
        chunks = await self.client.messages.create(**kwargs)
        async for event in _translate(chunks):
            yield event


async def _translate(
    chunks: AsyncIterable[RawMessageStreamEvent],
) -> AsyncIterator[AgentEvent]:
    """Convert Anthropic raw stream events into `AgentEvent`s.

    Tool-call arguments arrive as `input_json_delta` fragments between a
    `content_block_start` and `content_block_stop`; we accumulate by block
    index and emit `ToolCallRequested` on stop.
    """
    pending: dict[int, _PendingToolCall] = {}
    async for chunk in chunks:
        if chunk.type == "content_block_start":
            block = chunk.content_block
            if block.type == "tool_use":
                pending[chunk.index] = _PendingToolCall(id=block.id, name=block.name)
        elif chunk.type == "content_block_delta":
            delta = chunk.delta
            if delta.type == "text_delta":
                yield TextDelta(text=delta.text)
            elif delta.type == "input_json_delta":
                slot = pending.get(chunk.index)
                if slot is not None:
                    slot.arguments += delta.partial_json
        elif chunk.type == "content_block_stop":
            slot = pending.pop(chunk.index, None)
            if slot is not None:
                yield ToolCallRequested(
                    tool_call=ToolCall(id=slot.id, name=slot.name, arguments=slot.arguments)
                )


@dataclass
class _PendingToolCall:
    id: str
    name: str
    arguments: str = ""


def _to_api_messages(
    messages: Sequence[Message],
) -> tuple[str, list[dict[str, Any]]]:
    """Pull leading `system` messages aside; convert and collapse the rest.

    Returns `(system_prompt, api_messages)`. Adjacent `tool`-role messages
    coalesce into a single `user` turn carrying their results as content
    blocks — that's the shape Anthropic expects.
    """
    system_chunks: list[str] = []
    rest: list[Message] = []
    for msg in messages:
        if msg.role == "system":
            system_chunks.append(msg.content)
        else:
            rest.append(msg)

    api_messages: list[dict[str, Any]] = []
    i = 0
    while i < len(rest):
        if rest[i].role == "tool":
            results: list[dict[str, Any]] = []
            while i < len(rest) and rest[i].role == "tool":
                results.append(_to_tool_result_block(rest[i]))
                i += 1
            api_messages.append({"role": "user", "content": results})
        else:
            api_messages.append(_to_api_message(rest[i]))
            i += 1

    return "\n\n".join(system_chunks), api_messages


def _to_api_message(msg: Message) -> dict[str, Any]:
    if msg.role == "user":
        return {"role": "user", "content": msg.content}
    if msg.role == "assistant":
        blocks: list[dict[str, Any]] = []
        if msg.content:
            blocks.append({"type": "text", "text": msg.content})
        for tc in msg.tool_calls:
            blocks.append(
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": json.loads(tc.arguments) if tc.arguments else {},
                }
            )
        return {"role": "assistant", "content": blocks}
    if msg.role == "system" or msg.role == "tool":
        raise AssertionError(f"_to_api_message: role={msg.role!r} filtered upstream")
    assert_never(msg.role)


def _to_tool_result_block(msg: Message) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": msg.tool_call_id,
        "content": msg.content,
    }


def _to_api_tool(schema: ToolSchema) -> dict[str, Any]:
    return {
        "name": schema.name,
        "description": schema.description,
        "input_schema": schema.parameters,
    }
