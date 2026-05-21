"""Permission policies for tool calls."""

from termcoder.models import PermissionCheck, PermissionDecision, ToolCall


def allow_all() -> PermissionCheck:
    """Allow every tool call without prompting."""

    async def check(_call: ToolCall) -> PermissionDecision:
        return "allow"

    return check
