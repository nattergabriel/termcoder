"""Unit tests for the activate_skill tool."""

import json
from pathlib import Path
from typing import cast

from termcoder.models import ToolCall
from termcoder.skills.discovery import Skill, SkillRegistry
from termcoder.skills.tool import ActivateSkill


def _call(name: str) -> ToolCall:
    return ToolCall(id="c1", name="activate_skill", arguments=json.dumps({"name": name}))


async def test_activate_skill_schema_constrains_names_and_lists_catalog(tmp_path: Path) -> None:
    skill = Skill(
        name="python-testing",
        description="Use when writing Python tests.",
        location=tmp_path / "python-testing" / "SKILL.md",
        body="Test instructions.",
    )
    tool = ActivateSkill(SkillRegistry((skill,)))
    properties = cast(dict[str, dict[str, object]], tool.schema.parameters["properties"])

    assert tool.schema.name == "activate_skill"
    assert properties["name"]["enum"] == ("python-testing",)
    assert "python-testing: Use when writing Python tests." in tool.schema.description


async def test_activate_skill_returns_body_directory_and_resource_listing(tmp_path: Path) -> None:
    skill_dir = tmp_path / "python-testing"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("raw frontmatter should not be read", encoding="utf-8")
    (skill_dir / "scripts" / "run.py").write_text("print('ok')", encoding="utf-8")
    skill = Skill(
        name="python-testing",
        description="Use when writing Python tests.",
        location=skill_dir / "SKILL.md",
        body="# Instructions",
    )
    tool = ActivateSkill(SkillRegistry((skill,)))

    result = await tool.run(_call("python-testing"))

    assert result.is_error is False
    assert '<skill_content name="python-testing">' in result.content
    assert "# Instructions" in result.content
    assert "raw frontmatter" not in result.content
    assert f"Skill directory: {skill_dir}" in result.content
    assert "<file>scripts/run.py</file>" in result.content


async def test_activate_skill_unknown_name_is_tool_error(tmp_path: Path) -> None:
    skill = Skill(
        name="known",
        description="Known skill.",
        location=tmp_path / "known" / "SKILL.md",
        body="Body",
    )
    tool = ActivateSkill(SkillRegistry((skill,)))

    result = await tool.run(_call("missing"))

    assert result.is_error is True
    assert "unknown skill: missing" in result.content
