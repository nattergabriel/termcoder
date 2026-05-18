"""Permission policies — decide whether a tool call may run.

A `PermissionCheck` is what the agent loop awaits before dispatching every tool
call. `permissions.py` provides factories that build one for each policy mode.
`ask_each` defers every call to a user-supplied prompt callable wired in at
composition time; `allow_all` approves every call without prompting.
"""

from collections.abc import Awaitable, Callable

from termcoder.models import PermissionCheck, PermissionDecision, ToolCall

type PromptUser = Callable[[ToolCall], Awaitable[PermissionDecision]]


def ask_each(prompt: PromptUser) -> PermissionCheck:
    """Ask-before-each-tool-call: defer every decision to `prompt`."""

    async def check(call: ToolCall) -> PermissionDecision:
        return await prompt(call)

    return check


def allow_all() -> PermissionCheck:
    """Allow every tool call without prompting."""

    async def check(_call: ToolCall) -> PermissionDecision:
        return "allow"

    return check
