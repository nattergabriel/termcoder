"""Write tool."""

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, ToolArgs
from termcoder.tools.filesystem import required_path_arg
from termcoder.tools.protocol import ToolPermission
from termcoder.tools.results import invalid_arguments, tool_failed, tool_ok


class Write:
    permission: ToolPermission = "write"
    schema: ToolSchema = ToolSchema(
        name="write",
        description=(
            "Write UTF-8 text content to a file, creating parent directories as needed and "
            "overwriting any existing content."
        ),
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
            args = ToolArgs.from_call(call)
            path = required_path_arg(args, "path")
            content = args.required_string("content")
        except ArgumentError as exc:
            return invalid_arguments(call, exc)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            return tool_failed(call, "write", exc)
        return tool_ok(call, f"wrote {len(content)} characters to {path}")
