"""`/temperature` command."""

from collections.abc import Sequence

from termcoder.commands.context import CommandContext
from termcoder.commands.registry import SlashCommand, SlashCommandError


def temperature_command(context: CommandContext) -> SlashCommand:
    async def handle(args: Sequence[str]) -> str:
        if len(args) != 1:
            raise SlashCommandError("usage: /temperature <0.0-2.0>")
        try:
            temperature = float(args[0])
        except ValueError as exc:
            raise SlashCommandError("temperature must be a number") from exc
        if not 0 <= temperature <= 2:
            raise SlashCommandError("temperature must be between 0.0 and 2.0")
        context.set_temperature(temperature)
        return f"temperature set to {temperature:g} (persisted to {context.save_path})"

    return SlashCommand(name="temperature", handler=handle)
