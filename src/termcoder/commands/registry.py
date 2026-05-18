"""Slash-command dispatch for user-typed REPL directives like `/model gpt-4o-mini`.

Concrete commands live in sibling modules and register as small, bound handlers.
The registry only parses the command name, routes to the handler, and normalizes
user-facing errors as `SlashCommandError`.
"""

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from termcoder.errors import TermcoderError


class SlashCommandError(TermcoderError):
    """User-facing error from slash-command parsing or execution."""


type SlashHandler = Callable[[Sequence[str]], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class SlashCommand:
    """One registered slash command, bound to its handler at composition time."""

    name: str
    handler: SlashHandler


@dataclass(frozen=True, slots=True)
class SlashCommands:
    """Registry of slash commands. Built in the composition root, used by the REPL."""

    commands: Mapping[str, SlashCommand]

    @classmethod
    def from_iterable(cls, commands: Iterable[SlashCommand]) -> "SlashCommands":
        items = tuple(commands)
        indexed = {c.name: c for c in items}
        if len(indexed) != len(items):
            raise SlashCommandError("duplicate slash command name")
        return cls(commands=indexed)

    async def dispatch(self, line: str) -> str:
        """Parse a `/name args...` line and run its handler, returning the result message."""
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
