"""Tool protocol."""

from typing import Protocol

from termcoder.models import ToolCall, ToolName, ToolResult, ToolSchema


class Tool(Protocol):
    """A named, schema-described, callable tool."""

    name: ToolName
    schema: ToolSchema

    async def run(self, call: ToolCall) -> ToolResult: ...
