"""Reusable terminal interaction models."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ChoiceOption[T]:
    """One selectable answer in a terminal choice prompt."""

    label: str
    value: T
    shortcut: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ChoicePrompt[T]:
    """A small arrow-key navigable question rendered below active output."""

    title: str
    options: tuple[ChoiceOption[T], ...]
    default_index: int = 0
    footer: str = "Enter to select | Up/Down to move | Ctrl-C to cancel"

    def initial_state(self) -> "ChoicePromptState":
        if not self.options:
            raise ValueError("choice prompt requires at least one option")
        if not 0 <= self.default_index < len(self.options):
            raise ValueError("choice prompt default_index is out of range")
        return ChoicePromptState(prompt=self, selected_index=self.default_index)


@dataclass(slots=True)
class ChoicePromptState:
    """Mutable selection state for an active choice prompt."""

    prompt: ChoicePrompt[Any]
    selected_index: int
