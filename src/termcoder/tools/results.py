"""Helpers for constructing tool results."""

from termcoder.models import ToolCall, ToolResult


def invalid_arguments(call: ToolCall, exc: Exception) -> ToolResult:
    """Return a standard invalid-arguments tool error."""
    return tool_error(call, f"invalid arguments: {exc}")


def tool_failed(call: ToolCall, tool_name: str, exc: Exception) -> ToolResult:
    """Return a standard tool failure result."""
    return tool_error(call, f"{tool_name} failed: {exc}")


def tool_error(call: ToolCall, content: str) -> ToolResult:
    """Return a tool error with user-facing content."""
    return ToolResult(tool_call_id=call.id, content=content, is_error=True)
