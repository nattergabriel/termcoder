"""Write tool."""

from pathlib import Path

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, parse_object, required_string
from termcoder.tools.results import invalid_arguments, tool_failed


class Write:
    schema: ToolSchema = ToolSchema(
        name="write",
        description="Write UTF-8 text content to a file, overwriting any existing content.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Filesystem path to write to.",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write.",
                },
            },
            "required": ["path", "content"],
        },
    )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = parse_object(call)
            path = required_string(args, "path")
            content = required_string(args, "content")
        except ArgumentError as exc:
            return invalid_arguments(call, exc)
        try:
            Path(path).write_text(content, encoding="utf-8")
        except (OSError, TypeError) as exc:
            return tool_failed(call, "write", exc)
        return ToolResult(
            tool_call_id=call.id,
            content=f"wrote {len(content)} characters to {path}",
        )
