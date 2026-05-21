"""Unit tests for slash commands that mutate runtime settings."""

from pathlib import Path

import pytest

from termcoder.agent.loop import Agent
from termcoder.commands.context import CommandContext
from termcoder.commands.model import model_command
from termcoder.commands.provider import provider_command
from termcoder.commands.registry import SlashCommandError
from termcoder.commands.temperature import temperature_command
from termcoder.config import Config, load_config
from termcoder.models import PermissionDecision, ToolCall
from termcoder.tools.registry import Registry
from tests.fakes.fake_provider import FakeProvider


def _context(tmp_path: Path) -> CommandContext:
    provider = FakeProvider(scripts=[], model="initial", temperature=0.7)
    agent = Agent(
        provider=provider,
        registry=Registry([]),
        check_permission=_allow,
    )
    return CommandContext(agent=agent, config=Config(), save_path=tmp_path / "config.toml")


async def _allow(_call: ToolCall) -> PermissionDecision:
    return "allow"


async def test_model_command_mutates_provider_and_persists(tmp_path: Path) -> None:
    context = _context(tmp_path)

    result = await model_command(context).handler(["replaced"])

    assert context.agent.provider.model == "replaced"
    assert context.config.model == "replaced"
    assert "replaced" in result
    reloaded = load_config(cwd=tmp_path / "elsewhere", user_config_path=context.save_path)
    assert reloaded.model == "replaced"


async def test_model_command_rejects_zero_or_multiple_args(tmp_path: Path) -> None:
    context = _context(tmp_path)
    handler = model_command(context).handler

    with pytest.raises(SlashCommandError, match="usage"):
        await handler([])
    with pytest.raises(SlashCommandError, match="usage"):
        await handler(["one", "two"])

    assert context.agent.provider.model == "initial"
    assert not context.save_path.exists()


async def test_temperature_command_mutates_provider_and_persists(tmp_path: Path) -> None:
    context = _context(tmp_path)

    result = await temperature_command(context).handler(["0.2"])

    assert context.agent.provider.temperature == pytest.approx(0.2)
    assert context.config.temperature == pytest.approx(0.2)
    assert "0.2" in result
    reloaded = load_config(cwd=tmp_path / "elsewhere", user_config_path=context.save_path)
    assert reloaded.temperature == pytest.approx(0.2)


async def test_temperature_command_rejects_invalid_values(tmp_path: Path) -> None:
    context = _context(tmp_path)
    handler = temperature_command(context).handler

    with pytest.raises(SlashCommandError, match="number"):
        await handler(["hot"])
    with pytest.raises(SlashCommandError, match="between"):
        await handler(["3"])

    assert context.agent.provider.temperature == pytest.approx(0.7)
    assert not context.save_path.exists()


async def test_provider_command_rebuilds_provider_and_persists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context(tmp_path)
    built_configs: list[Config] = []

    def build_fake(config: Config) -> FakeProvider:
        built_configs.append(config)
        return FakeProvider(
            scripts=[],
            model=config.model,
            temperature=config.temperature,
        )

    monkeypatch.setattr("termcoder.commands.context.build_provider", build_fake)

    result = await provider_command(context).handler(["anthropic"])

    assert context.config.provider == "anthropic"
    assert context.agent.provider is not None
    assert built_configs[-1].provider == "anthropic"
    assert "anthropic" in result
    reloaded = load_config(cwd=tmp_path / "elsewhere", user_config_path=context.save_path)
    assert reloaded.provider == "anthropic"


async def test_provider_command_rejects_unknown_provider(tmp_path: Path) -> None:
    context = _context(tmp_path)

    with pytest.raises(SlashCommandError, match="unknown provider"):
        await provider_command(context).handler(["cohere"])

    assert context.config.provider == "openai"
    assert not context.save_path.exists()
