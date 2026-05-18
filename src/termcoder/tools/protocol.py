"""Tool Protocol — the seam between the agent loop and any callable tool.

A `Tool` advertises a `name` and a JSON-schema `schema` (the description sent
to the provider), and runs against a `ToolCall` to produce a `ToolResult`.

Tools return failures as `ToolResult(is_error=True, content=...)` rather than
raising — file-not-found, non-zero exits, JSON parse errors are all normal
LLM input, not exceptions. Only genuine system failures (e.g. the event loop
crashing) propagate.
"""

from typing import Protocol

from termcoder.models import ToolCall, ToolName, ToolResult, ToolSchema


class Tool(Protocol):
    """A named, schema-described, callable tool."""

    name: ToolName
    schema: ToolSchema

    async def run(self, call: ToolCall) -> ToolResult: ...
