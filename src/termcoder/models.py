"""Shared domain types."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Literal

type Role = Literal["system", "user", "assistant", "tool"]
type ToolName = str
type PermissionDecision = Literal["allow", "deny"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A request from the assistant to invoke a tool."""

    id: str
    name: ToolName
    arguments: str


type PermissionCheck = Callable[[ToolCall], Awaitable[PermissionDecision]]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of running a tool."""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class Message:
    """One entry in the conversation log."""

    role: Role
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True, slots=True)
class ToolSchema:
    """JSON Schema description of a tool."""

    name: ToolName
    description: str
    parameters: Mapping[str, object]
