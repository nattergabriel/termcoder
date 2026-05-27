"""Tool protocol."""

from typing import Literal, Protocol

from termcoder.models import ToolCall, ToolResult, ToolSchema

type ToolPermission = Literal["always", "readonly", "write", "execute"]


class Tool(Protocol):
    """A named, schema-described, callable tool."""

    schema: ToolSchema
    permission: ToolPermission

    async def run(self, call: ToolCall) -> ToolResult: ...
