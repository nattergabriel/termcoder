"""Permission policies for tool calls."""

from collections.abc import Iterable

from termcoder.models import PermissionCheck, PermissionDecision, ToolCall, ToolName


def ask_each(
    prompt_user: PermissionCheck,
    *,
    always_allowed_tools: Iterable[ToolName] = (),
) -> PermissionCheck:
    """Prompt for every tool call except always-allowed tools."""
    return _allow_tools_without_prompt(prompt_user, always_allowed_tools)


def allow_readonly(
    prompt_user: PermissionCheck,
    *,
    always_allowed_tools: Iterable[ToolName] = (),
    readonly_tools: Iterable[ToolName] = (),
) -> PermissionCheck:
    """Allow read-only tool calls without prompting."""
    return _allow_tools_without_prompt(prompt_user, (*always_allowed_tools, *readonly_tools))


def _allow_tools_without_prompt(
    prompt_user: PermissionCheck,
    tool_names: Iterable[ToolName],
) -> PermissionCheck:
    """Return a policy that auto-allows the given tools before prompting."""
    allowed_tools = frozenset(tool_names)

    async def check(call: ToolCall) -> PermissionDecision:
        if call.name in allowed_tools:
            return "allow"
        return await prompt_user(call)

    return check


async def allow_all(_call: ToolCall) -> PermissionDecision:
    """Allow every tool call without prompting."""
    return "allow"
