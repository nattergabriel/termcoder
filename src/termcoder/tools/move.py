"""Move tool."""

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, ToolArgs
from termcoder.tools.results import invalid_arguments, tool_error, tool_failed, tool_ok


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
            args = ToolArgs.from_call(call)
            source = args.required_path("source")
            destination = args.required_path("destination")
            overwrite = args.bool("overwrite", default=False)
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        if destination.exists() and not overwrite:
            return tool_error(call, f"move failed: {destination} already exists")
        try:
            source.replace(destination)
        except OSError as exc:
            return tool_failed(call, "move", exc)
        return tool_ok(call, f"moved {source} to {destination}")
