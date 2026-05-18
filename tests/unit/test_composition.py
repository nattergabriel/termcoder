"""Unit tests for composition-root wiring that isn't covered by integration tests."""

from pathlib import Path

import pytest

from termcoder.composition import _model_command, build
from termcoder.config import load_config
from termcoder.slash_commands import SlashCommandError
from termcoder.types import PermissionDecision, ToolCall
from tests.fakes.fake_provider import FakeProvider


async def _stub_prompt(_call: ToolCall) -> PermissionDecision:
    return "allow"


async def test_model_command_mutates_provider_and_persists(tmp_path: Path) -> None:
    provider = FakeProvider(scripts=[], model="initial")
    save_path = tmp_path / "config.toml"

    result = await _model_command(provider, save_path).handler(["replaced"])

    assert provider.model == "replaced"
    assert "replaced" in result
    reloaded = load_config(cwd=tmp_path / "elsewhere", user_config_path=save_path)
    assert reloaded.model == "replaced"


async def test_model_command_rejects_zero_or_multiple_args(tmp_path: Path) -> None:
    provider = FakeProvider(scripts=[], model="initial")
    save_path = tmp_path / "config.toml"
    handler = _model_command(provider, save_path).handler

    with pytest.raises(SlashCommandError, match="usage"):
        await handler([])
    with pytest.raises(SlashCommandError, match="usage"):
        await handler(["one", "two"])

    assert provider.model == "initial"
    assert not save_path.exists()


def test_max_iterations_flows_from_config_to_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Skip the real SDK client construction — we only care that the value lands on Agent.
    monkeypatch.setattr(
        "termcoder.composition.build_provider", lambda _cfg: FakeProvider(scripts=[])
    )
    user_path = tmp_path / "config.toml"
    user_path.write_text("max_iterations = 7\n", encoding="utf-8")
    config = load_config(cwd=tmp_path / "elsewhere", user_config_path=user_path)

    ctx = build(config, _stub_prompt)

    assert ctx.agent.max_iterations == 7
