"""Unit tests for the slash-command registry and dispatcher."""

from collections.abc import Sequence

import pytest

from termcoder.commands.registry import (
    SlashCommand,
    SlashCommandError,
    SlashCommands,
)


def _record(received: list[Sequence[str]], reply: str = "ok") -> SlashCommand:
    async def handle(args: Sequence[str]) -> str:
        received.append(tuple(args))
        return reply

    return SlashCommand(name="echo", handler=handle)


async def test_dispatch_routes_to_registered_handler() -> None:
    received: list[Sequence[str]] = []
    commands = SlashCommands.from_iterable([_record(received, reply="echoed")])

    result = await commands.dispatch("/echo foo bar")

    assert result == "echoed"
    assert received == [("foo", "bar")]


async def test_dispatch_strips_surrounding_whitespace() -> None:
    received: list[Sequence[str]] = []
    commands = SlashCommands.from_iterable([_record(received)])

    await commands.dispatch("   /echo   alpha   beta   ")

    assert received == [("alpha", "beta")]


async def test_dispatch_unknown_command_raises() -> None:
    commands = SlashCommands.from_iterable([])

    with pytest.raises(SlashCommandError, match="/nope"):
        await commands.dispatch("/nope")


def test_duplicate_command_names_raise() -> None:
    with pytest.raises(SlashCommandError, match="duplicate"):
        SlashCommands.from_iterable(
            [
                SlashCommand(name="same", handler=_record([]).handler),
                SlashCommand(name="same", handler=_record([]).handler),
            ]
        )


def test_names_returns_registered_commands_in_display_order() -> None:
    commands = SlashCommands.from_iterable(
        [
            SlashCommand(name="model", handler=_record([]).handler),
            SlashCommand(name="provider", handler=_record([]).handler),
        ]
    )

    assert commands.names() == ("model", "provider")


async def test_dispatch_empty_slash_raises() -> None:
    commands = SlashCommands.from_iterable([])

    with pytest.raises(SlashCommandError, match="missing command"):
        await commands.dispatch("/   ")


async def test_dispatch_non_slash_input_raises() -> None:
    commands = SlashCommands.from_iterable([])

    with pytest.raises(SlashCommandError, match="not a slash command"):
        await commands.dispatch("hello")


async def test_handler_error_propagates_as_slash_command_error() -> None:
    async def handle(args: Sequence[str]) -> str:
        raise SlashCommandError("usage: /boom")

    commands = SlashCommands.from_iterable([SlashCommand(name="boom", handler=handle)])

    with pytest.raises(SlashCommandError, match="usage: /boom"):
        await commands.dispatch("/boom")
