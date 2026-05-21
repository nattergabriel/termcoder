"""Tool registry."""

from collections.abc import Iterable, Sequence

from termcoder.models import ToolName, ToolSchema
from termcoder.tools.protocol import Tool


class Registry:
    """Tool lookup by name."""

    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools = {t.schema.name: t for t in tools}

    def get(self, name: ToolName) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> Sequence[ToolSchema]:
        return tuple(t.schema for t in self._tools.values())
