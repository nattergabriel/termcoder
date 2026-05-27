"""Tool registry."""

from collections.abc import Iterable, Sequence

from termcoder.models import ToolName, ToolSchema
from termcoder.tools.protocol import Tool, ToolPermission


class Registry:
    """Tool lookup by name."""

    __slots__ = ("_tools",)

    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[ToolName, Tool] = {tool.schema.name: tool for tool in tools}

    def get(self, name: ToolName) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> Sequence[ToolSchema]:
        return tuple(tool.schema for tool in self._tools.values())

    def names_with_permission(self, permission: ToolPermission) -> frozenset[ToolName]:
        return frozenset(
            tool.schema.name for tool in self._tools.values() if tool.permission == permission
        )
