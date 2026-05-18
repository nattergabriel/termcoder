"""Provider protocol."""

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from termcoder.events import AgentEvent
from termcoder.models import Message, ToolSchema


class Provider(Protocol):
    model: str
    """Model identifier."""

    temperature: float
    """Sampling temperature."""

    def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSchema],
    ) -> AsyncIterator[AgentEvent]: ...
