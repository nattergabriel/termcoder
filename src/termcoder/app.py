"""Application composition root."""

from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from termcoder.agent.loop import Agent
from termcoder.agent.prompt import assemble_system_prompt
from termcoder.commands.context import CommandContext
from termcoder.commands.model import model_command
from termcoder.commands.provider import provider_command
from termcoder.commands.registry import SlashCommands
from termcoder.commands.temperature import temperature_command
from termcoder.config import Config, default_user_config_path
from termcoder.instructions import load_agent_instruction_files
from termcoder.models import PermissionCheck
from termcoder.permissions import allow_all, allow_readonly, ask_each
from termcoder.providers.registry import build_provider
from termcoder.skills import SkillCatalog, discover_skills
from termcoder.skills.tool import ActivateSkill
from termcoder.tools.builtins import builtin_tools
from termcoder.tools.registry import Registry


@dataclass(frozen=True, slots=True)
class AppContext:
    """Runtime objects for one REPL session."""

    agent: Agent
    config: Config
    slash_commands: SlashCommands
    skills: SkillCatalog


def build(
    config: Config,
    prompt_user: PermissionCheck,
    *,
    cwd: Path | None = None,
) -> AppContext:
    provider = build_provider(config)
    skills = discover_skills(cwd)
    tools = list(builtin_tools())
    if skills.skills:
        tools.append(ActivateSkill(skills))
    registry = Registry(tools)
    instruction_files = load_agent_instruction_files(cwd)
    agent = Agent(
        provider=provider,
        registry=registry,
        check_permission=_permission_check(config, prompt_user, registry),
        system_prompt=assemble_system_prompt(
            config.system_prompt,
            instruction_files=instruction_files,
        ),
        max_iterations=config.max_iterations,
    )
    command_context = CommandContext(
        agent=agent,
        config=config,
        save_path=default_user_config_path(),
    )
    slash_commands = SlashCommands.from_iterable(
        [
            model_command(command_context),
            provider_command(command_context),
            temperature_command(command_context),
        ]
    )
    return AppContext(agent=agent, config=config, slash_commands=slash_commands, skills=skills)


def _permission_check(
    config: Config,
    prompt_user: PermissionCheck,
    registry: Registry,
) -> PermissionCheck:
    always_allowed_tools = registry.names_with_permission("always")
    readonly_tools = registry.names_with_permission("readonly")
    match config.permission_mode:
        case "ask_each":
            return ask_each(prompt_user, always_allowed_tools=always_allowed_tools)
        case "allow_readonly":
            return allow_readonly(
                prompt_user,
                always_allowed_tools=always_allowed_tools,
                readonly_tools=readonly_tools,
            )
        case "allow_all":
            return allow_all
    assert_never(config.permission_mode)
