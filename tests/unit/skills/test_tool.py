"""Unit tests for the activate_skill tool."""

import json
from pathlib import Path

from termcoder.models import ToolCall
from termcoder.skills import ActivateSkill, Skill, SkillCatalog


def _tool(tmp_path: Path) -> ActivateSkill:
    skill_dir = tmp_path / "python-testing"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("", encoding="utf-8")
    (scripts_dir / "run.py").write_text("print('ok')\n", encoding="utf-8")
    catalog = SkillCatalog(
        (
            Skill(
                name="python-testing",
                description="Write Python tests.",
                location=skill_dir / "SKILL.md",
                body="# Python Testing\nUse pytest.",
            ),
        )
    )
    return ActivateSkill(catalog)


def test_activate_skill_schema_constrains_name_to_discovered_skills(tmp_path: Path) -> None:
    schema = _tool(tmp_path).schema

    assert schema.name == "activate_skill"
    assert "python-testing: Write Python tests." in schema.description
    properties = schema.parameters["properties"]
    assert isinstance(properties, dict)
    name_schema = properties["name"]
    assert isinstance(name_schema, dict)
    assert name_schema["enum"] == ["python-testing"]


async def test_activate_skill_returns_wrapped_body_directory_and_resources(tmp_path: Path) -> None:
    tool = _tool(tmp_path)
    call = ToolCall(
        id="s1",
        name="activate_skill",
        arguments=json.dumps({"name": "python-testing"}),
    )

    result = await tool.run(call)

    assert result.is_error is False
    assert '<skill_content name="python-testing">' in result.content
    assert "# Python Testing\nUse pytest." in result.content
    assert f"Skill directory: {tmp_path / 'python-testing'}" in result.content
    assert "<file>scripts/run.py</file>" in result.content
    assert "name: python-testing" not in result.content


async def test_activate_skill_unknown_name_returns_tool_error(tmp_path: Path) -> None:
    result = await _tool(tmp_path).run(
        ToolCall(id="s1", name="activate_skill", arguments=json.dumps({"name": "missing"}))
    )

    assert result.is_error is True
    assert "unknown skill: missing" in result.content
