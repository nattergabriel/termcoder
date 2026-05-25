"""Permission policies for tool calls."""

from termcoder.models import PermissionCheck, PermissionDecision, ToolCall, ToolName

_ALWAYS_ALLOWED_TOOLS: frozenset[ToolName] = frozenset({"activate_skill"})
_READ_ONLY_TOOLS: frozenset[ToolName] = frozenset({"read", "search"})


def ask_each(prompt_user: PermissionCheck) -> PermissionCheck:
    """Prompt for every tool call except always-allowed tools."""
    return _allow_tools_without_prompt(prompt_user, _ALWAYS_ALLOWED_TOOLS)


def allow_readonly(prompt_user: PermissionCheck) -> PermissionCheck:
    """Allow read-only tool calls without prompting."""
    return _allow_tools_without_prompt(prompt_user, _ALWAYS_ALLOWED_TOOLS | _READ_ONLY_TOOLS)


def _allow_tools_without_prompt(
    prompt_user: PermissionCheck,
    tool_names: frozenset[ToolName],
) -> PermissionCheck:
    """Return a policy that auto-allows the given tools before prompting."""

    async def check(call: ToolCall) -> PermissionDecision:
        if call.name in tool_names:
            return "allow"
        return await prompt_user(call)

    return check


async def allow_all(_call: ToolCall) -> PermissionDecision:
    """Allow every tool call without prompting."""
    return "allow"
