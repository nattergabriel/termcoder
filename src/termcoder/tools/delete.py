"""Delete tool."""

import shutil
from pathlib import Path

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import (
    ArgumentError,
    optional_bool,
    parse_object,
    required_string,
)
from termcoder.tools.results import invalid_arguments, tool_error, tool_failed


class Delete:
    schema: ToolSchema = ToolSchema(
        name="delete",
        description="Delete a file, symlink, or directory.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File, symlink, or directory to delete.",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Required to delete directories. Defaults to false.",
                },
            },
            "required": ["path"],
        },
    )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = parse_object(call)
            path = Path(required_string(args, "path"))
            recursive = optional_bool(args, "recursive", default=False)
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        try:
            if path.is_dir() and not path.is_symlink():
                if not recursive:
                    return tool_error(call, "delete failed: directories require recursive=true")
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            return tool_failed(call, "delete", exc)
        return ToolResult(tool_call_id=call.id, content=f"deleted {path}")
