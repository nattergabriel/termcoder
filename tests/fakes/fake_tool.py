"""Scripted `Tool` for tests.

`FakeTool(name=..., scripted_results=[...])` returns one pre-arranged
`ToolResult` per `run()` call (matched positionally) and records every
`ToolCall` it received on `received`. The default schema is the smallest
valid object schema; tests can override when they care.
"""

from dataclasses import dataclass, field

from termcoder.types import ToolCall, ToolName, ToolResult, ToolSchema


@dataclass
class FakeTool:
    """Plays scripted `ToolResult`s and records each call."""

    name: ToolName = "fake"
    scripted_results: list[ToolResult] = field(default_factory=list)
    received: list[ToolCall] = field(default_factory=list)
    schema: ToolSchema = field(init=False)

    def __post_init__(self) -> None:
        self.schema = ToolSchema(
            name=self.name,
            description=f"fake tool {self.name}",
            parameters={"type": "object", "properties": {}},
        )

    async def run(self, call: ToolCall) -> ToolResult:
        self.received.append(call)
        if not self.scripted_results:
            return ToolResult(tool_call_id=call.id, content="ok")
        scripted = self.scripted_results.pop(0)
        # Override the tool_call_id so tests don't have to predict it.
        return ToolResult(
            tool_call_id=call.id,
            content=scripted.content,
            is_error=scripted.is_error,
        )
