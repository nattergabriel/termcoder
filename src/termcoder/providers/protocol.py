"""Provider Protocol — the seam between the agent loop and any LLM backend.

A `Provider` takes a conversation prefix (including any tool-role `ToolResult`
messages from prior rounds) plus the catalog of tools the model may call, and
returns an async iterator of `AgentEvent`s. The loop drives it with
`async for event in provider.stream(...)`. Both `async def`-yield bodies and
plain `def` returning a pre-built async iterator satisfy the Protocol.
"""

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from termcoder.events import AgentEvent
from termcoder.types import Message, ToolSchema


class Provider(Protocol):
    model: str
    """The model identifier the provider will request. Mutable so `/model` can swap it live."""

    def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSchema],
    ) -> AsyncIterator[AgentEvent]: ...
