"""Bash tool."""

import asyncio

from termcoder.models import ToolCall, ToolName, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, parse_object, required_string


class Bash:
    name: ToolName = "bash"
    schema: ToolSchema = ToolSchema(
        name="bash",
        description=(
            "Run a shell command via /bin/sh and return its combined stdout, stderr, and exit code."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute.",
                },
            },
            "required": ["command"],
        },
    )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = parse_object(call)
            command = required_string(args, "command")
        except ArgumentError as exc:
            return ToolResult(
                tool_call_id=call.id,
                content=f"invalid arguments: {exc}",
                is_error=True,
            )

        proc = await asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
        exit_line = f"[exit {proc.returncode}]"
        content = f"{output}\n{exit_line}" if output else exit_line
        return ToolResult(
            tool_call_id=call.id,
            content=content,
            is_error=proc.returncode != 0,
        )
