"""Scripted `Provider` for tests.

`FakeProvider(scripts=[...])` plays one pre-arranged `AgentEvent` list per call
to `stream()`. Multi-turn conversations (model asks for a tool, loop runs it,
model continues) need one script per provider invocation.

`received_calls` records each call eagerly — before iteration starts — so tests
can assert what messages and tools the loop sent without having to drain the
stream first.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field

from termcoder.events import AgentEvent
from termcoder.models import Message, ToolSchema


@dataclass
class FakeProvider:
    """Plays scripted `AgentEvent` streams, one script per `stream()` call."""

    scripts: list[list[AgentEvent]]
    model: str = "fake-model"
    temperature: float = 0.7
    received_calls: list[tuple[tuple[Message, ...], tuple[ToolSchema, ...]]] = field(
        default_factory=list
    )

    def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSchema],
    ) -> AsyncIterator[AgentEvent]:
        self.received_calls.append((tuple(messages), tuple(tools)))
        if not self.scripts:
            raise RuntimeError(
                "FakeProvider has no more scripts — stream() was called more times than expected"
            )
        return _replay(self.scripts.pop(0))


async def _replay(events: list[AgentEvent]) -> AsyncIterator[AgentEvent]:
    for event in events:
        yield event
