"""Unit tests for permission policies."""

from termcoder.models import PermissionDecision, ToolCall
from termcoder.permissions import ask_each


async def test_ask_each_delegates_to_prompt_callable() -> None:
    received: list[ToolCall] = []

    async def prompt(call: ToolCall) -> PermissionDecision:
        received.append(call)
        return "allow"

    check = ask_each(prompt)
    call = ToolCall(id="c1", name="read", arguments="{}")
    decision = await check(call)

    assert decision == "allow"
    assert received == [call]


async def test_ask_each_passes_through_denial() -> None:
    async def prompt(_: ToolCall) -> PermissionDecision:
        return "deny"

    check = ask_each(prompt)
    decision = await check(ToolCall(id="c1", name="read", arguments="{}"))
    assert decision == "deny"
