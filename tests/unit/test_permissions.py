"""Unit tests for permission policies."""

from termcoder.models import PermissionDecision, ToolCall
from termcoder.permissions import allow_all, ask_each


async def test_ask_each_allows_read_without_prompt() -> None:
    called = False

    async def prompt(_call: ToolCall) -> PermissionDecision:
        nonlocal called
        called = True
        return "deny"

    check = ask_each(prompt)

    decision = await check(ToolCall(id="c1", name="read", arguments='{"path":"x"}'))

    assert decision == "allow"
    assert called is False


async def test_ask_each_allows_search_without_prompt() -> None:
    called = False

    async def prompt(_call: ToolCall) -> PermissionDecision:
        nonlocal called
        called = True
        return "deny"

    check = ask_each(prompt)

    decision = await check(
        ToolCall(id="c1", name="search", arguments='{"path":".","query":"needle"}')
    )

    assert decision == "allow"
    assert called is False


async def test_ask_each_prompts_for_sensitive_tools() -> None:
    received: list[ToolCall] = []

    async def prompt(call: ToolCall) -> PermissionDecision:
        received.append(call)
        return "deny"

    check = ask_each(prompt)
    call = ToolCall(id="c1", name="bash", arguments='{"command":"true"}')

    decision = await check(call)

    assert decision == "deny"
    assert received == [call]


async def test_ask_each_prompts_for_unknown_tools() -> None:
    received: list[ToolCall] = []

    async def prompt(call: ToolCall) -> PermissionDecision:
        received.append(call)
        return "allow"

    check = ask_each(prompt)
    call = ToolCall(id="c1", name="future_tool", arguments="{}")

    decision = await check(call)

    assert decision == "allow"
    assert received == [call]


async def test_allow_all_returns_allow_without_prompt() -> None:
    decision = await allow_all(ToolCall(id="c1", name="bash", arguments='{"command":"true"}'))

    assert decision == "allow"
