"""Tool registry — name lookup and schema export.

Built once at the composition root from the concrete `Tool` instances; the
agent loop queries by name when dispatching tool calls and pulls all schemas
to advertise the catalog to the provider.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from termcoder.models import ToolName, ToolSchema
from termcoder.tools.protocol import Tool


@dataclass(slots=True)
class Registry:
    """`ToolName` → `Tool` map with helpers for the two access patterns we have."""

    tools: dict[ToolName, Tool] = field(default_factory=dict)

    @classmethod
    def from_iterable(cls, tools: Iterable[Tool]) -> "Registry":
        return cls(tools={t.name: t for t in tools})

    def get(self, name: ToolName) -> Tool | None:
        return self.tools.get(name)

    def schemas(self) -> Sequence[ToolSchema]:
        return tuple(t.schema for t in self.tools.values())
