"""Write tool — write text content to a file, overwriting any existing content.

Parent directories must already exist; missing-parent and permission errors
come back as a `ToolResult` with `is_error=True`.
"""

from pathlib import Path

from termcoder.models import ToolCall, ToolName, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, parse_object, required_string


class Write:
    name: ToolName = "write"
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
            return ToolResult(
                tool_call_id=call.id,
                content=f"invalid arguments: {exc}",
                is_error=True,
            )
        try:
            Path(path).write_text(content, encoding="utf-8")
        except (OSError, TypeError) as exc:
            return ToolResult(
                tool_call_id=call.id,
                content=f"write failed: {exc}",
                is_error=True,
            )
        return ToolResult(
            tool_call_id=call.id,
            content=f"wrote {len(content)} characters to {path}",
        )
