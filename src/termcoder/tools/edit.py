"""Edit tool."""

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, ToolArgs
from termcoder.tools.filesystem import required_path_arg
from termcoder.tools.protocol import ToolPermission
from termcoder.tools.results import invalid_arguments, tool_error, tool_failed, tool_ok


class Edit:
    permission: ToolPermission = "write"
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
            args = ToolArgs.from_call(call)
            path = required_path_arg(args, "path")
            old = args.required_string("old")
            new = args.required_string("new")
            replace_all = args.bool("replace_all", default=False)
            if old == "":
                raise ArgumentError("'old' must not be empty")
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
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
            path.write_text(updated, encoding="utf-8")
        except OSError as exc:
            return tool_failed(call, "edit", exc)
        return tool_ok(call, f"replaced {replacements} occurrence(s) in {path}")
