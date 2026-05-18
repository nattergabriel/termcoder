"""`/model` command."""

from collections.abc import Sequence

from termcoder.commands.context import CommandContext
from termcoder.commands.registry import SlashCommand, SlashCommandError


def model_command(context: CommandContext) -> SlashCommand:
    async def handle(args: Sequence[str]) -> str:
        if len(args) != 1:
            raise SlashCommandError("usage: /model <name>")
        model = args[0]
        context.set_model(model)
        return f"model set to {model} (persisted to {context.save_path})"

    return SlashCommand(name="model", handler=handle)
