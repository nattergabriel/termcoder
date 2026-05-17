"""Conversation state — the running message log fed back to the provider on each round.

Append-only by design: every user input, assistant turn, and tool result lands
here in order. The provider sees `messages` on each `stream()` call; the TUI
can render the same list as a transcript. No partials live here — the loop
finalizes each assistant message (text + tool calls) before appending it.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from termcoder.types import Message, ToolCall, ToolResult


@dataclass(slots=True)
class State:
    """The conversation log: every message exchanged so far, in order."""

    _messages: list[Message] = field(default_factory=list)

    @property
    def messages(self) -> Sequence[Message]:
        return tuple(self._messages)

    def append_system(self, content: str) -> None:
        self._messages.append(Message(role="system", content=content))

    def append_user(self, content: str) -> None:
        self._messages.append(Message(role="user", content=content))

    def append_assistant(self, content: str, tool_calls: Iterable[ToolCall] = ()) -> None:
        self._messages.append(
            Message(role="assistant", content=content, tool_calls=tuple(tool_calls))
        )

    def append_tool_result(self, result: ToolResult) -> None:
        self._messages.append(
            Message(role="tool", content=result.content, tool_call_id=result.tool_call_id)
        )
