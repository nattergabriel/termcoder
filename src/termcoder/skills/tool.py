"""activate_skill tool."""

import os
from html import escape
from pathlib import Path

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.skills.discovery import Skill, SkillRegistry
from termcoder.tools.arguments import ArgumentError, parse_object, required_string
from termcoder.tools.results import invalid_arguments, tool_error

_RESOURCE_LIMIT = 50
_IGNORED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
}


class ActivateSkill:
    """Load full instructions for a discovered skill."""

    def __init__(self, skills: SkillRegistry) -> None:
        self._skills = skills
        self.schema = ToolSchema(
            name="activate_skill",
            description=(
                "Load full instructions for one available Agent Skill. When a task matches "
                "a skill description, call this tool before proceeding.\n\n"
                f"Available skills:\n{_catalog(skills)}"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": skills.names(),
                        "description": "Name of the skill to activate.",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = parse_object(call)
            name = required_string(args, "name")
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        skill = self._skills.get(name)
        if skill is None:
            return tool_error(call, f"unknown skill: {name}")
        return ToolResult(tool_call_id=call.id, content=render_skill_content(skill))


def render_skill_content(skill: Skill) -> str:
    """Render skill body and resource metadata for tool or inline activation."""
    resources, truncated = _resource_paths(skill.directory)
    lines = [
        f'<skill_content name="{escape(skill.name, quote=True)}">',
        skill.body,
        "",
        f"Skill directory: {skill.directory}",
        "Relative paths in this skill are relative to the skill directory.",
        "<skill_resources>",
    ]
    lines.extend(f"  <file>{escape(path)}</file>" for path in resources)
    if truncated:
        lines.append("  <truncated>true</truncated>")
    lines.extend(["</skill_resources>", "</skill_content>"])
    return "\n".join(lines)


def _catalog(skills: SkillRegistry) -> str:
    return "\n".join(f"- {skill.name}: {skill.description}" for skill in skills.all())


def _resource_paths(directory: Path) -> tuple[tuple[str, ...], bool]:
    paths: list[str] = []
    truncated = False
    for root, dirnames, filenames in os.walk(directory):
        dirnames[:] = sorted(name for name in dirnames if name not in _IGNORED_DIR_NAMES)
        for filename in sorted(filenames):
            path = Path(root) / filename
            if path.name == "SKILL.md":
                continue
            try:
                relative = path.relative_to(directory)
            except ValueError:
                continue
            if len(paths) >= _RESOURCE_LIMIT:
                truncated = True
                return tuple(paths), truncated
            paths.append(relative.as_posix())
    return tuple(paths), truncated
