"""Permission policies — decide whether a tool call may run.

A `PermissionCheck` is what the agent loop awaits before dispatching every tool
call. `permissions.py` provides factories that build one for each policy mode.
At v0.1 only `ask_each` is implemented — every call defers to a user-supplied
prompt callable wired in at composition time. Future modes (allowlist,
deny_list, auto_approve_safe) join here as short functions of the same shape.
"""

from collections.abc import Awaitable, Callable

from termcoder.models import PermissionCheck, PermissionDecision, ToolCall

type PromptUser = Callable[[ToolCall], Awaitable[PermissionDecision]]


def ask_each(prompt: PromptUser) -> PermissionCheck:
    """Ask-before-each-tool-call: defer every decision to `prompt`."""

    async def check(call: ToolCall) -> PermissionDecision:
        return await prompt(call)

    return check
