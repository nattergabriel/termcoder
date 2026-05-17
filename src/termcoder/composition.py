"""Composition root — wires every layer together.

Reads `Config`, builds the OpenAI client, the tool registry, and the permission
policy, then assembles the `Agent`. The agent and permission layers never
import a concrete provider, tool, or UI — everything they need arrives as
constructor args here.
"""

import os
from dataclasses import dataclass
from typing import assert_never

from openai import AsyncOpenAI

from termcoder.agent.loop import Agent
from termcoder.agent.prompt import assemble_system_prompt
from termcoder.config import Config
from termcoder.permissions import PromptUser, ask_each
from termcoder.providers.openai_compatible import OpenAICompatibleProvider
from termcoder.tools.bash import Bash
from termcoder.tools.read import Read
from termcoder.tools.registry import Registry
from termcoder.tools.write import Write
from termcoder.types import PermissionCheck


@dataclass(frozen=True, slots=True)
class AppContext:
    """A ready-to-run session: the agent plus the config it was built from."""

    agent: Agent
    config: Config


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
    return AppContext(agent=agent, config=config)


def _permission_check(config: Config, prompt_user: PromptUser) -> PermissionCheck:
    if config.permission_mode == "ask_each":
        return ask_each(prompt_user)
    assert_never(config.permission_mode)
