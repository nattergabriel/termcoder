"""Tool registry."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from termcoder.models import ToolName, ToolSchema
from termcoder.tools.protocol import Tool


@dataclass(slots=True)
class Registry:
    """Tool lookup by name."""

    tools: dict[ToolName, Tool] = field(default_factory=dict)

    @classmethod
    def from_iterable(cls, tools: Iterable[Tool]) -> "Registry":
        return cls(tools={t.name: t for t in tools})

    def get(self, name: ToolName) -> Tool | None:
        return self.tools.get(name)

    def schemas(self) -> Sequence[ToolSchema]:
        return tuple(t.schema for t in self.tools.values())
