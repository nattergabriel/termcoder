"""Agent loop."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import assert_never

from termcoder.agent.prompt import DEFAULT_SYSTEM_PROMPT
from termcoder.agent.state import State
from termcoder.errors import TermcoderError
from termcoder.events import (
    AgentEvent,
    TextDelta,
    ToolCallCompleted,
    ToolCallRequested,
    ToolCallStarted,
    TurnComplete,
)
from termcoder.models import Message, PermissionCheck, ToolCall, ToolResult
from termcoder.providers.protocol import Provider
from termcoder.tools.registry import Registry

type ProviderEvent = TextDelta | ToolCallRequested


@dataclass
class Agent:
    """Per-conversation orchestrator: provider + tools + permission policy + state."""

    provider: Provider
    registry: Registry
    check_permission: PermissionCheck
    state: State = field(default_factory=State)
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_iterations: int = 25
    """Cap on provider rounds per turn."""

    def __post_init__(self) -> None:
        if not self.system_prompt:
            self.system_prompt = DEFAULT_SYSTEM_PROMPT

    async def run_turn(self, user_input: str) -> AsyncIterator[AgentEvent]:
        checkpoint = len(self.state.messages)
        try:
            self.state.append(Message(role="user", content=user_input))
            for _ in range(self.max_iterations):
                assistant_text_parts: list[str] = []
                tool_calls: list[ToolCall] = []
                async for provider_event in self._provider_events():
                    match provider_event:
                        case TextDelta():
                            assistant_text_parts.append(provider_event.text)
                        case ToolCallRequested():
                            tool_calls.append(provider_event.tool_call)
                        case _:
                            assert_never(provider_event)
                    yield provider_event

                self.state.append(
                    Message(
                        role="assistant",
                        content="".join(assistant_text_parts),
                        tool_calls=tuple(tool_calls),
                    )
                )

                if not tool_calls:
                    yield TurnComplete()
                    return

                async for tool_event in self._dispatch_all(tool_calls):
                    yield tool_event

            raise TermcoderError(
                f"agent exceeded max_iterations={self.max_iterations} without completing the turn"
            )
        except BaseException:
            # Drop partial turn state after cancellation or failure.
            self.state.truncate(checkpoint)
            raise

    async def _provider_events(self) -> AsyncIterator[ProviderEvent]:
        async for event in self.provider.stream(
            self._messages_for_provider(), self.registry.schemas()
        ):
            match event:
                case TextDelta() | ToolCallRequested():
                    yield event
                case ToolCallStarted() | ToolCallCompleted() | TurnComplete():
                    # These events are emitted by the loop, not providers.
                    raise TermcoderError(f"provider emitted unexpected event: {event!r}")
                case _:
                    assert_never(event)

    async def _dispatch_all(
        self, calls: list[ToolCall]
    ) -> AsyncIterator[ToolCallStarted | ToolCallCompleted]:
        for call in calls:
            async for event in self._dispatch(call):
                if isinstance(event, ToolCallCompleted):
                    self.state.append(
                        Message(
                            role="tool",
                            content=event.result.content,
                            tool_call_id=event.result.tool_call_id,
                        )
                    )
                yield event

    async def _dispatch(self, call: ToolCall) -> AsyncIterator[ToolCallStarted | ToolCallCompleted]:
        decision = await self.check_permission(call)
        if decision == "deny":
            yield ToolCallCompleted(
                result=ToolResult(
                    tool_call_id=call.id,
                    content="User denied permission to run this tool.",
                    is_error=True,
                )
            )
            return
        tool = self.registry.get(call.name)
        if tool is None:
            yield ToolCallCompleted(
                result=ToolResult(
                    tool_call_id=call.id,
                    content=f"unknown tool: {call.name}",
                    is_error=True,
                )
            )
            return
        yield ToolCallStarted(tool_call=call)
        yield ToolCallCompleted(result=await tool.run(call))

    def _messages_for_provider(self) -> list[Message]:
        return [Message(role="system", content=self.system_prompt), *self.state.messages]
