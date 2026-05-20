"""Reusable terminal interaction models."""

from dataclasses import dataclass


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
