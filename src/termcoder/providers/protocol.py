"""Provider Protocol — the seam between the agent loop and any LLM backend.

A `Provider` takes a conversation prefix (including any tool-role `ToolResult`
messages from prior rounds) plus the catalog of tools the model may call, and
returns an async iterator of `AgentEvent`s describing what happens as the model
responds. The loop drives it with `async for event in provider.stream(...)`.

Implementations vary in shape: an `async def` body that yields events is the
natural fit for live streaming SDKs, while a non-async `def` returning a
pre-built async iterator suits scripted test doubles. Both satisfy this
Protocol.
"""

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from termcoder.events import AgentEvent
from termcoder.types import Message, ToolSchema


class Provider(Protocol):
    """Streams `AgentEvent`s from a conversation prefix and a tool catalog."""

    def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSchema],
    ) -> AsyncIterator[AgentEvent]: ...
