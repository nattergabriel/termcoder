"""Tool protocol."""

from typing import Protocol

from termcoder.models import ToolCall, ToolResult, ToolSchema


class Tool(Protocol):
    """A named, schema-described, callable tool."""

    schema: ToolSchema

    async def run(self, call: ToolCall) -> ToolResult: ...
