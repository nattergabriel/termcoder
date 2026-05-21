"""Unit tests for permission policies."""

from termcoder.models import ToolCall
from termcoder.permissions import allow_all


async def test_allow_all_returns_allow_without_prompt() -> None:
    check = allow_all()

    decision = await check(ToolCall(id="c1", name="bash", arguments='{"command":"true"}'))

    assert decision == "allow"
