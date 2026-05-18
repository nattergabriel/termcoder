"""Agent loop — drives the provider, dispatches tools, gates each call on permission.

System errors (provider unreachable, registry bugs) raise; tool failures and
denials surface as `ToolResult(is_error=True)` so the model can react.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from termcoder.agent.prompt import assemble_system_prompt
from termcoder.agent.state import State
from termcoder.errors import TermcoderError
from termcoder.events import (
    AgentEvent,
    TextDelta,
    ToolCallCompleted,
    ToolCallRequested,
    TurnComplete,
)
from termcoder.providers.protocol import Provider
from termcoder.tools.registry import Registry
from termcoder.types import Message, PermissionCheck, ToolCall, ToolResult


@dataclass
class Agent:
    """Per-conversation orchestrator: provider + tools + permission policy + state."""

    provider: Provider
    registry: Registry
    check_permission: PermissionCheck
    state: State = field(default_factory=State)
    system_prompt: str = field(default_factory=assemble_system_prompt)
    max_iterations: int = 25
    """Cap on provider rounds per turn — stops runaway tool-call loops."""

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
                        case _:
                            # ToolCallCompleted / TurnComplete are loop-owned; a provider
                            # yielding them is a contract violation, not a routine event.
                            raise TermcoderError(f"provider emitted unexpected event: {event!r}")

                self.state.append_assistant(assistant_text, tool_calls)

                if not tool_calls:
                    yield TurnComplete()
                    return

                for tool_call in tool_calls:
                    result = await self._dispatch(tool_call)
                    self.state.append_tool_result(result)
                    yield ToolCallCompleted(result=result)

            raise TermcoderError(
                f"agent exceeded max_iterations={self.max_iterations} without completing the turn"
            )
        except BaseException:
            # Any abnormal exit — cancellation, provider error, max_iterations,
            # generator close — leaves a half-finished turn in the log. Roll
            # state back to the checkpoint so the next turn starts clean.
            self.state.truncate(checkpoint)
            raise

    async def _dispatch(self, call: ToolCall) -> ToolResult:
        decision = await self.check_permission(call)
        if decision == "deny":
            return ToolResult(
                tool_call_id=call.id,
                content="User denied permission to run this tool.",
                is_error=True,
            )
        tool = self.registry.get(call.name)
        if tool is None:
            return ToolResult(
                tool_call_id=call.id,
                content=f"unknown tool: {call.name}",
                is_error=True,
            )
        return await tool.run(call)

    def _messages_for_provider(self) -> list[Message]:
        if not self.system_prompt:
            return list(self.state.messages)
        return [Message(role="system", content=self.system_prompt), *self.state.messages]
