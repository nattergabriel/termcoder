"""OpenAI Chat Completions streaming provider — works with any compatible endpoint.

Translates between our `Message` / `ToolSchema` / `AgentEvent` types and the OpenAI
SDK's wire shapes. Every `openai.*` import stays inside this module; the agent
core never sees vendor types.

The configured `base_url` on the `AsyncOpenAI` client determines which endpoint
gets called (OpenAI, OpenRouter, Groq, local llama.cpp, …). That wiring lives
in the composition root; this module just adapts the protocol.
"""

from collections.abc import AsyncIterable, AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, assert_never

from openai import AsyncOpenAI, Omit, omit
from openai.types.chat import ChatCompletionChunk

from termcoder.events import AgentEvent, TextDelta, ToolCallRequested
from termcoder.types import Message, ToolCall, ToolSchema


@dataclass
class OpenAICompatibleProvider:
    """Streams `AgentEvent`s from the OpenAI Chat Completions API."""

    client: AsyncOpenAI
    model: str
    temperature: float = 0.7
    max_tokens: int | None = None

    async def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSchema],
    ) -> AsyncIterator[AgentEvent]:
        api_messages: list[Any] = [_to_api_message(m) for m in messages]
        api_tools: list[Any] | Omit = [_to_api_tool(t) for t in tools] if tools else omit
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "tools": api_tools,
            "stream": True,
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        chunks = await self.client.chat.completions.create(**kwargs)
        async for event in _translate(chunks):
            yield event


async def _translate(
    chunks: AsyncIterable[ChatCompletionChunk],
) -> AsyncIterator[AgentEvent]:
    """Convert OpenAI streaming chunks into `AgentEvent`s.

    Tool-call arguments arrive in fragments across chunks; we accumulate them
    by their `index` slot and emit each finished `ToolCallRequested` once the
    chunk stream ends.
    """
    pending: dict[int, _PendingToolCall] = {}
    async for chunk in chunks:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            yield TextDelta(text=delta.content)
        for tc_delta in delta.tool_calls or []:
            slot = pending.setdefault(tc_delta.index, _PendingToolCall())
            if tc_delta.id:
                slot.id = tc_delta.id
            if tc_delta.function is not None:
                if tc_delta.function.name:
                    slot.name = tc_delta.function.name
                if tc_delta.function.arguments:
                    slot.arguments += tc_delta.function.arguments
    for index in sorted(pending):
        slot = pending[index]
        yield ToolCallRequested(
            tool_call=ToolCall(id=slot.id, name=slot.name, arguments=slot.arguments)
        )


@dataclass
class _PendingToolCall:
    id: str = ""
    name: str = ""
    arguments: str = ""


def _to_api_message(msg: Message) -> dict[str, Any]:
    if msg.role == "system" or msg.role == "user":
        return {"role": msg.role, "content": msg.content}
    if msg.role == "assistant":
        result: dict[str, Any] = {"role": "assistant", "content": msg.content or None}
        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in msg.tool_calls
            ]
        return result
    if msg.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": msg.tool_call_id,
            "content": msg.content,
        }
    assert_never(msg.role)


def _to_api_tool(schema: ToolSchema) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": schema.name,
            "description": schema.description,
            "parameters": schema.parameters,
        },
    }
