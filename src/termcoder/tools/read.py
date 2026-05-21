"""Read tool."""

from pathlib import Path

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, optional_int, parse_object, required_string
from termcoder.tools.results import invalid_arguments, tool_failed


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
            args = parse_object(call)
            path = required_string(args, "path")
            start_line = optional_int(args, "start_line")
            limit = optional_int(args, "limit")
            if start_line is not None and start_line < 1:
                raise ArgumentError("'start_line' must be at least 1")
            if limit is not None and limit < 1:
                raise ArgumentError("'limit' must be at least 1")
        except ArgumentError as exc:
            return invalid_arguments(call, exc)
        try:
            content = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, TypeError) as exc:
            return tool_failed(call, "read", exc)
        if start_line is not None or limit is not None:
            content = _line_window(content, start_line=start_line, limit=limit)
        return ToolResult(tool_call_id=call.id, content=content)


def _line_window(content: str, *, start_line: int | None, limit: int | None) -> str:
    lines = content.splitlines(keepends=True)
    start_index = (start_line or 1) - 1
    end_index = None if limit is None else start_index + limit
    return "".join(lines[start_index:end_index])
