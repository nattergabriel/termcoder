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
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    user_path = tmp_path / "config.toml"
    user_path.write_text("max_iterations = 7\n", encoding="utf-8")
    config = load_config(cwd=tmp_path / "elsewhere", user_config_path=user_path)

    ctx = build(config, _stub_prompt)

    assert ctx.agent.max_iterations == 7


def test_default_tools_are_registered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("termcoder.app.build_provider", lambda _cfg: FakeProvider(scripts=[]))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    ctx = build(Config(), _stub_prompt, cwd=tmp_path / "project")

    assert {schema.name for schema in ctx.agent.registry.schemas()} == {
        "read",
        "write",
        "edit",
        "bash",
        "search",
        "patch",
        "list_files",
        "move",
        "delete",
    }


def test_activate_skill_tool_is_registered_when_skills_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("termcoder.app.build_provider", lambda _cfg: FakeProvider(scripts=[]))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    skill = tmp_path / "project" / ".termcoder" / "skills" / "python-testing" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: python-testing\ndescription: Write Python tests.\n---\nUse pytest.\n",
        encoding="utf-8",
    )

    ctx = build(Config(), _stub_prompt, cwd=tmp_path / "project")

    assert "activate_skill" in {schema.name for schema in ctx.agent.registry.schemas()}
    assert ctx.skills.names() == ("python-testing",)


async def test_allow_all_permission_mode_bypasses_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("termcoder.app.build_provider", lambda _cfg: FakeProvider(scripts=[]))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    called = False

    async def prompt(_call: ToolCall) -> PermissionDecision:
        nonlocal called
        called = True
        return "deny"

    ctx = build(Config(permission_mode="allow_all"), prompt)
    decision = await ctx.agent.check_permission(ToolCall(id="c1", name="read", arguments="{}"))

    assert decision == "allow"
    assert called is False


async def test_allow_readonly_permission_mode_skips_read_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("termcoder.app.build_provider", lambda _cfg: FakeProvider(scripts=[]))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    called = False

    async def prompt(_call: ToolCall) -> PermissionDecision:
        nonlocal called
        called = True
        return "deny"

    ctx = build(Config(permission_mode="allow_readonly"), prompt)
    decision = await ctx.agent.check_permission(ToolCall(id="c1", name="read", arguments="{}"))

    assert decision == "allow"
    assert called is False


async def test_ask_each_permission_mode_prompts_for_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("termcoder.app.build_provider", lambda _cfg: FakeProvider(scripts=[]))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    called = False

    async def prompt(_call: ToolCall) -> PermissionDecision:
        nonlocal called
        called = True
        return "deny"

    ctx = build(Config(permission_mode="ask_each"), prompt)
    decision = await ctx.agent.check_permission(ToolCall(id="c1", name="read", arguments="{}"))

    assert decision == "deny"
    assert called is True


def test_agents_md_instructions_flow_to_agent_system_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("termcoder.app.build_provider", lambda _cfg: FakeProvider(scripts=[]))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    nested = tmp_path / "pkg"
    nested.mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("Root instructions.\n", encoding="utf-8")
    (nested / "AGENTS.md").write_text("Nested instructions.\n", encoding="utf-8")

    ctx = build(Config(system_prompt="User config instructions."), _stub_prompt, cwd=nested)

    assert "Root instructions." in ctx.agent.system_prompt
    assert "Nested instructions." in ctx.agent.system_prompt
    assert ctx.agent.system_prompt.index("Root instructions.") < ctx.agent.system_prompt.index(
        "Nested instructions."
    )
    assert ctx.agent.system_prompt.index("Nested instructions.") < ctx.agent.system_prompt.index(
        "User config instructions."
    )
