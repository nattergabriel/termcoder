"""Edit tool."""

from pathlib import Path

from termcoder.models import ToolCall, ToolName, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, optional_bool, parse_object, required_string
from termcoder.tools.results import invalid_arguments, tool_error, tool_failed


class Edit:
    name: ToolName = "edit"
    schema: ToolSchema = ToolSchema(
        name="edit",
        description=(
            "Edit a UTF-8 text file by replacing an exact text match. "
            "By default the match must occur exactly once."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Filesystem path to the file to edit.",
                },
                "old": {
                    "type": "string",
                    "description": "Exact existing text to replace. Must not be empty.",
                },
                "new": {
                    "type": "string",
                    "description": "Replacement text.",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "When true, replace every occurrence instead of requiring one.",
                },
            },
            "required": ["path", "old", "new"],
        },
    )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = parse_object(call)
            path = required_string(args, "path")
            old = required_string(args, "old")
            new = required_string(args, "new")
            replace_all = optional_bool(args, "replace_all", default=False)
            if old == "":
                raise ArgumentError("'old' must not be empty")
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        target = Path(path)
        try:
            content = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, TypeError) as exc:
            return tool_failed(call, "edit", exc)

        count = content.count(old)
        if count == 0:
            return tool_error(call, "edit failed: old text was not found")
        if count > 1 and not replace_all:
            return tool_error(
                call,
                content=(
                    f"edit failed: old text matched {count} times; "
                    "use replace_all=true or provide a more specific match"
                ),
            )

        replacements = count if replace_all else 1
        updated = content.replace(old, new, replacements)
        try:
            target.write_text(updated, encoding="utf-8")
        except (OSError, TypeError) as exc:
            return tool_failed(call, "edit", exc)
        return ToolResult(
            tool_call_id=call.id,
            content=f"replaced {replacements} occurrence(s) in {path}",
        )
