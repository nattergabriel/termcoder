"""Agent loop."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import assert_never

from termcoder.agent.prompt import assemble_system_prompt
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


@dataclass
class Agent:
    """Per-conversation orchestrator: provider + tools + permission policy + state."""

    provider: Provider
    registry: Registry
    check_permission: PermissionCheck
    state: State = field(default_factory=State)
    system_prompt: str = field(default_factory=assemble_system_prompt)
    max_iterations: int = 25
    """Cap on provider rounds per turn."""

    async def run_turn(self, user_input: str) -> AsyncIterator[AgentEvent]:
        checkpoint = len(self.state.messages)
        try:
            self.state.append_user(user_input)
            for _ in range(self.max_iterations):
                assistant_text = ""
                tool_calls: list[ToolCall] = []
                async for event in self.provider.stream(
                    self._messages_for_provider(), self.registry.schemas()
                ):
                    match event:
                        case TextDelta():
                            assistant_text += event.text
                            yield event
                        case ToolCallRequested():
                            tool_calls.append(event.tool_call)
                            yield event
                        case ToolCallStarted() | ToolCallCompleted() | TurnComplete():
                            # These events are emitted by the loop, not providers.
                            raise TermcoderError(f"provider emitted unexpected event: {event!r}")
                        case _:
                            assert_never(event)

                self.state.append_assistant(assistant_text, tool_calls)

                if not tool_calls:
                    yield TurnComplete()
                    return

                for tool_call in tool_calls:
                    async for event in self._dispatch(tool_call):
                        match event:
                            case ToolCallCompleted():
                                self.state.append_tool_result(event.result)
                            case ToolCallStarted():
                                pass
                        yield event

            raise TermcoderError(
                f"agent exceeded max_iterations={self.max_iterations} without completing the turn"
            )
        except BaseException:
            # Drop partial turn state after cancellation or failure.
            self.state.truncate(checkpoint)
            raise

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
        if not self.system_prompt:
            return list(self.state.messages)
        return [Message(role="system", content=self.system_prompt), *self.state.messages]
