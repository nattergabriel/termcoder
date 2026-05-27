"""Move tool."""

from pathlib import Path

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import (
    ArgumentError,
    optional_bool,
    parse_object,
    required_string,
)
from termcoder.tools.results import invalid_arguments, tool_error, tool_failed


class Move:
    schema: ToolSchema = ToolSchema(
        name="move",
        description="Move or rename a file or directory.",
        parameters={
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Existing file or directory to move.",
                },
                "destination": {
                    "type": "string",
                    "description": "New path for the file or directory.",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Replace an existing destination when true. Defaults to false.",
                },
            },
            "required": ["source", "destination"],
        },
    )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = parse_object(call)
            source = Path(required_string(args, "source"))
            destination = Path(required_string(args, "destination"))
            overwrite = optional_bool(args, "overwrite", default=False)
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        if destination.exists() and not overwrite:
            return tool_error(call, f"move failed: {destination} already exists")
        try:
            source.replace(destination)
        except OSError as exc:
            return tool_failed(call, "move", exc)
        return ToolResult(tool_call_id=call.id, content=f"moved {source} to {destination}")
