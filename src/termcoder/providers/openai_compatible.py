"""OpenAI-compatible Chat Completions provider."""

import os
from collections.abc import AsyncIterable, AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, assert_never

from openai import AsyncOpenAI, Omit, omit
from openai.types.chat import ChatCompletionChunk

from termcoder.config import Config
from termcoder.events import AgentEvent, TextDelta, ToolCallRequested
from termcoder.models import Message, ToolCall, ToolSchema


@dataclass
class OpenAICompatibleProvider:
    client: AsyncOpenAI
    model: str
    temperature: float
    max_tokens: int | None = None

    async def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSchema],
    ) -> AsyncIterator[AgentEvent]:
        api_messages: list[Any] = [_to_api_message(m) for m in messages]
        api_tools: list[Any] | Omit = [_to_api_tool(t) for t in tools] if tools else omit
        chunks = await self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            tools=api_tools,
            stream=True,
            temperature=self.temperature,
            max_tokens=self.max_tokens if self.max_tokens is not None else omit,
        )
        async for event in _translate(chunks):
            yield event


async def _translate(
    chunks: AsyncIterable[ChatCompletionChunk],
) -> AsyncIterator[AgentEvent]:
    """Convert streaming chunks into agent events."""
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
    match msg.role:
        case "system" | "user":
            return {"role": msg.role, "content": msg.content}
        case "assistant":
            # OpenAI requires null when an assistant message carries only tool calls.
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
        case "tool":
            return {
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content,
            }
        case _:
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


def from_config(config: Config) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        client=AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
        ),
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
