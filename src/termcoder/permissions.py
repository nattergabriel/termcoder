"""Permission policies for tool calls."""

from termcoder.models import PermissionCheck, PermissionDecision, ToolCall, ToolName

_READ_ONLY_TOOLS: frozenset[ToolName] = frozenset({"read", "search"})


def ask_each(prompt_user: PermissionCheck) -> PermissionCheck:
    """Prompt for every tool call."""
    return prompt_user


def allow_readonly(prompt_user: PermissionCheck) -> PermissionCheck:
    """Allow read-only tool calls without prompting."""

    async def check(call: ToolCall) -> PermissionDecision:
        if call.name in _READ_ONLY_TOOLS:
            return "allow"
        return await prompt_user(call)

    return check


async def allow_all(_call: ToolCall) -> PermissionDecision:
    """Allow every tool call without prompting."""
    return "allow"
