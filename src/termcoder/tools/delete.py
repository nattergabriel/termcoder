"""Delete tool."""

import shutil

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, ToolArgs
from termcoder.tools.results import invalid_arguments, tool_error, tool_failed, tool_ok


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
            args = ToolArgs.from_call(call)
            path = args.required_path("path")
            recursive = args.bool("recursive", default=False)
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
        return tool_ok(call, f"deleted {path}")
