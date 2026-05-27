"""Bash tool."""

import asyncio

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, ToolArgs
from termcoder.tools.results import invalid_arguments, tool_error, tool_failed

_DEFAULT_TIMEOUT_SECONDS = 30
_DEFAULT_MAX_CHARS = 20_000


class Bash:
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
                "cwd": {
                    "type": "string",
                    "description": (
                        "Directory to run the command in. Defaults to current directory."
                    ),
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": (
                        "Seconds before killing the command. "
                        f"Defaults to {_DEFAULT_TIMEOUT_SECONDS}."
                    ),
                },
                "max_chars": {
                    "type": "integer",
                    "description": f"Maximum output characters. Defaults to {_DEFAULT_MAX_CHARS}.",
                },
            },
            "required": ["command"],
        },
    )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = ToolArgs.from_call(call)
            command = args.required_string("command")
            cwd = args.optional_string("cwd")
            timeout = args.int("timeout_seconds", default=_DEFAULT_TIMEOUT_SECONDS, minimum=1)
            max_chars = args.int("max_chars", default=_DEFAULT_MAX_CHARS, minimum=1)
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            return tool_failed(call, "bash", exc)

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return tool_error(call, f"bash timed out after {timeout} second(s)")

        output = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
        exit_line = f"[exit {proc.returncode}]"
        content = f"{output}\n{exit_line}" if output else exit_line
        if len(content) > max_chars:
            content = f"{content[:max_chars]}\n[truncated to {max_chars} characters]"
        return ToolResult(
            tool_call_id=call.id,
            content=content,
            is_error=proc.returncode != 0,
        )
