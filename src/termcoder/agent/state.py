"""Conversation log."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from termcoder.models import Message, ToolCall, ToolResult


@dataclass(slots=True)
class State:
    """Messages exchanged so far."""

    _messages: list[Message] = field(default_factory=list)

    @property
    def messages(self) -> Sequence[Message]:
        return tuple(self._messages)

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

    def truncate(self, length: int) -> None:
        """Drop messages appended after a known-good checkpoint."""
        del self._messages[length:]
