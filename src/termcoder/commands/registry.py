"""Slash-command dispatch."""

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from termcoder.errors import TermcoderError


class SlashCommandError(TermcoderError):
    """User-facing error from slash-command parsing or execution."""


type SlashHandler = Callable[[Sequence[str]], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class SlashCommand:
    """One registered slash command."""

    name: str
    handler: SlashHandler


@dataclass(frozen=True, slots=True)
class SlashCommands:
    """Registry of slash commands."""

    commands: Mapping[str, SlashCommand]

    @classmethod
    def from_iterable(cls, commands: Iterable[SlashCommand]) -> "SlashCommands":
        items = tuple(commands)
        indexed = {c.name: c for c in items}
        if len(indexed) != len(items):
            raise SlashCommandError("duplicate slash command name")
        return cls(commands=indexed)

    async def dispatch(self, line: str) -> str:
        """Parse and dispatch a slash command."""
        stripped = line.strip()
        if not stripped.startswith("/"):
            raise SlashCommandError(f"not a slash command: {line!r}")
        parts = stripped[1:].split()
        if not parts:
            raise SlashCommandError("missing command name after '/'")
        name, *args = parts
        cmd = self.commands.get(name)
        if cmd is None:
            raise SlashCommandError(f"unknown command: /{name}")
        return await cmd.handler(args)
