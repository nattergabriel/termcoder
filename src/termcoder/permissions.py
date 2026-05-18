"""Permission policies for tool calls."""

from collections.abc import Awaitable, Callable

from termcoder.models import PermissionCheck, PermissionDecision, ToolCall

type PromptUser = Callable[[ToolCall], Awaitable[PermissionDecision]]


def ask_each(prompt: PromptUser) -> PermissionCheck:
    """Prompt before each tool call."""

    async def check(call: ToolCall) -> PermissionDecision:
        return await prompt(call)

    return check


def allow_all() -> PermissionCheck:
    """Allow every tool call without prompting."""

    async def check(_call: ToolCall) -> PermissionDecision:
        return "allow"

    return check
