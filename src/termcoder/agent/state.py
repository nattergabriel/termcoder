"""Conversation log."""

from dataclasses import dataclass, field

from termcoder.models import Message


@dataclass(slots=True)
class State:
    """Messages exchanged so far."""

    _messages: list[Message] = field(default_factory=list)

    @property
    def messages(self) -> tuple[Message, ...]:
        return tuple(self._messages)

    def __len__(self) -> int:
        return len(self._messages)

    def append(self, message: Message) -> None:
        self._messages.append(message)

    def truncate(self, length: int) -> None:
        """Drop messages appended after a known-good checkpoint."""
        del self._messages[length:]
