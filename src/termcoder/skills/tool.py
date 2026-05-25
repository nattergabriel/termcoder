"""Skill activation tool."""

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.skills.catalog import SkillCatalog
from termcoder.tools.arguments import ArgumentError, parse_object, required_string
from termcoder.tools.results import invalid_arguments, tool_error


class ActivateSkill:
    """Return body-only instructions for a discovered skill."""

    def __init__(self, catalog: SkillCatalog) -> None:
        self._catalog = catalog
        self.schema = ToolSchema(
            name="activate_skill",
            description=(
                "Load full instructions for one available Agent Skill. "
                "Use this when the task matches a skill description.\n\n"
                f"{catalog.compact_catalog()}"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The skill name to activate.",
                        "enum": list(catalog.names()),
                    }
                },
                "required": ["name"],
            },
        )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = parse_object(call)
            name = required_string(args, "name")
        except ArgumentError as exc:
            return invalid_arguments(call, exc)
        content = self._catalog.activation_content(name)
        if content is None:
            return tool_error(call, f"unknown skill: {name}")
        return ToolResult(tool_call_id=call.id, content=content)
