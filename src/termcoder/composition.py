"""Composition root — wires every layer together.

Reads `Config`, builds the OpenAI client, the tool registry, and the permission
policy, then assembles the `Agent`. The agent and permission layers never
import a concrete provider, tool, or UI — everything they need arrives as
constructor args here.
"""

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from openai import AsyncOpenAI

from termcoder.agent.loop import Agent
from termcoder.agent.prompt import assemble_system_prompt
from termcoder.config import Config, default_user_config_path, save_setting
from termcoder.permissions import PromptUser, ask_each
from termcoder.providers.openai_compatible import OpenAICompatibleProvider
from termcoder.slash_commands import SlashCommand, SlashCommandError, SlashCommands
from termcoder.tools.bash import Bash
from termcoder.tools.read import Read
from termcoder.tools.registry import Registry
from termcoder.tools.write import Write
from termcoder.types import PermissionCheck


@dataclass(frozen=True, slots=True)
class AppContext:
    """A ready-to-run session: the agent, its config, and the slash-command registry."""

    agent: Agent
    config: Config
    slash_commands: SlashCommands


def build(config: Config, prompt_user: PromptUser) -> AppContext:
    client = AsyncOpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )
    provider = OpenAICompatibleProvider(
        client=client,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    registry = Registry.from_iterable([Read(), Write(), Bash()])
    agent = Agent(
        provider=provider,
        registry=registry,
        check_permission=_permission_check(config, prompt_user),
        system_prompt=assemble_system_prompt(config.system_prompt),
    )
    slash_commands = SlashCommands.from_iterable(
        [_model_command(provider, default_user_config_path())]
    )
    return AppContext(agent=agent, config=config, slash_commands=slash_commands)


def _permission_check(config: Config, prompt_user: PromptUser) -> PermissionCheck:
    if config.permission_mode == "ask_each":
        return ask_each(prompt_user)
    assert_never(config.permission_mode)


def _model_command(provider: OpenAICompatibleProvider, save_path: Path) -> SlashCommand:
    """`/model <name>` — swap the live provider's model and persist to `save_path`."""

    async def handle(args: Sequence[str]) -> str:
        if len(args) != 1:
            raise SlashCommandError("usage: /model <name>")
        name = args[0]
        provider.model = name
        save_setting("model", name, path=save_path)
        return f"model set to {name} (persisted to {save_path})"

    return SlashCommand(name="model", handler=handle)
