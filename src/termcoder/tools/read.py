"""Read tool."""

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, ToolArgs
from termcoder.tools.results import invalid_arguments, tool_failed, tool_ok


class Read:
    schema: ToolSchema = ToolSchema(
        name="read",
        description="Read a UTF-8 text file, optionally returning a 1-based line window.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Filesystem path to the file to read.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional 1-based first line to return.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional maximum number of lines to return.",
                },
            },
            "required": ["path"],
        },
    )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = ToolArgs.from_call(call)
            path = args.required_path("path")
            start_line = args.optional_int("start_line", minimum=1)
            limit = args.optional_int("limit", minimum=1)
        except ArgumentError as exc:
            return invalid_arguments(call, exc)
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return tool_failed(call, "read", exc)
        if start_line is not None or limit is not None:
            content = _line_window(content, start_line=start_line, limit=limit)
        return tool_ok(call, content)


def _line_window(content: str, *, start_line: int | None, limit: int | None) -> str:
    lines = content.splitlines(keepends=True)
    start_index = (start_line or 1) - 1
    end_index = None if limit is None else start_index + limit
    return "".join(lines[start_index:end_index])
