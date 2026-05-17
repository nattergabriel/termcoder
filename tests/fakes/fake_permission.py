"""Scripted permission policy for tests.

`FakePermission(decisions=[...])` replays the list one decision per call. With
no script, it returns `default` ("allow") for every call. Either way, every
received `ToolCall` is recorded eagerly on `received` so tests can assert
ordering — useful for the mid-stream gating test in particular.
"""

from dataclasses import dataclass, field

from termcoder.types import PermissionDecision, ToolCall


@dataclass
class FakePermission:
    """Records each call; replies from `decisions` if set, otherwise `default`."""

    decisions: list[PermissionDecision] | None = None
    default: PermissionDecision = "allow"
    received: list[ToolCall] = field(default_factory=list)

    async def __call__(self, call: ToolCall) -> PermissionDecision:
        self.received.append(call)
        if self.decisions:
            return self.decisions.pop(0)
        return self.default
