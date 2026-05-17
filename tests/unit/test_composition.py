"""Unit tests for composition-root wiring that isn't covered by integration tests."""

from pathlib import Path

import pytest
from openai import AsyncOpenAI

from termcoder.composition import _model_command
from termcoder.config import load_config
from termcoder.providers.openai_compatible import OpenAICompatibleProvider
from termcoder.slash_commands import SlashCommandError


def _provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(client=AsyncOpenAI(api_key="test"), model="gpt-initial")


async def test_model_command_mutates_provider_and_persists(tmp_path: Path) -> None:
    provider = _provider()
    save_path = tmp_path / "config.toml"

    result = await _model_command(provider, save_path).handler(["gpt-replaced"])

    assert provider.model == "gpt-replaced"
    assert "gpt-replaced" in result
    reloaded = load_config(cwd=tmp_path / "elsewhere", user_config_path=save_path)
    assert reloaded.model == "gpt-replaced"


async def test_model_command_rejects_zero_or_multiple_args(tmp_path: Path) -> None:
    provider = _provider()
    save_path = tmp_path / "config.toml"
    handler = _model_command(provider, save_path).handler

    with pytest.raises(SlashCommandError, match="usage"):
        await handler([])
    with pytest.raises(SlashCommandError, match="usage"):
        await handler(["one", "two"])

    assert provider.model == "gpt-initial"
    assert not save_path.exists()
