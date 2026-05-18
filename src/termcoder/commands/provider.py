"""`/provider` command."""

from collections.abc import Sequence

from termcoder.commands.context import CommandContext
from termcoder.commands.registry import SlashCommand, SlashCommandError
from termcoder.providers.registry import provider_names


def provider_command(context: CommandContext) -> SlashCommand:
    async def handle(args: Sequence[str]) -> str:
        if len(args) != 1:
            raise SlashCommandError(f"usage: /provider <{'|'.join(provider_names())}>")
        provider = args[0]
        if provider not in provider_names():
            raise SlashCommandError(f"unknown provider: {provider}")
        context.set_provider(provider)
        return f"provider set to {provider} (persisted to {context.save_path})"

    return SlashCommand(name="provider", handler=handle)
