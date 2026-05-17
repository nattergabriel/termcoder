"""Read tool — return the contents of a UTF-8 text file at the given path.

Missing files, non-UTF-8 content, and permission errors come back as a
`ToolResult` with `is_error=True` so the model can react.
"""

import json
from pathlib import Path

from termcoder.types import ToolCall, ToolName, ToolResult, ToolSchema


class Read:
    name: ToolName = "read"
    schema: ToolSchema = ToolSchema(
        name="read",
        description="Read the contents of a UTF-8 text file at the given path.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Filesystem path to the file to read.",
                },
            },
            "required": ["path"],
        },
    )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = json.loads(call.arguments)
            path = args["path"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            return ToolResult(
                tool_call_id=call.id,
                content=f"invalid arguments: {exc}",
                is_error=True,
            )
        try:
            content = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, TypeError) as exc:
            return ToolResult(
                tool_call_id=call.id,
                content=f"read failed: {exc}",
                is_error=True,
            )
        return ToolResult(tool_call_id=call.id, content=content)
