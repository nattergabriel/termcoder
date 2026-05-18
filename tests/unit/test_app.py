"""Unit tests for app wiring that isn't covered by integration tests."""

from pathlib import Path

import pytest

from termcoder.app import build
from termcoder.config import Config, load_config
from termcoder.models import PermissionDecision, ToolCall
from tests.fakes.fake_provider import FakeProvider


async def _stub_prompt(_call: ToolCall) -> PermissionDecision:
    return "allow"


def test_max_iterations_flows_from_config_to_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Skip the real SDK client construction — we only care that the value lands on Agent.
    monkeypatch.setattr("termcoder.app.build_provider", lambda _cfg: FakeProvider(scripts=[]))
    user_path = tmp_path / "config.toml"
    user_path.write_text("max_iterations = 7\n", encoding="utf-8")
    config = load_config(cwd=tmp_path / "elsewhere", user_config_path=user_path)

    ctx = build(config, _stub_prompt)

    assert ctx.agent.max_iterations == 7


async def test_allow_all_permission_mode_bypasses_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("termcoder.app.build_provider", lambda _cfg: FakeProvider(scripts=[]))
    called = False

    async def prompt(_call: ToolCall) -> PermissionDecision:
        nonlocal called
        called = True
        return "deny"

    ctx = build(Config(permission_mode="allow_all"), prompt)
    decision = await ctx.agent.check_permission(ToolCall(id="c1", name="read", arguments="{}"))

    assert decision == "allow"
    assert called is False
