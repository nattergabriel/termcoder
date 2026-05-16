"""Shared domain types — the lingua franca passed across layers.

Pure data. No I/O, no behavior. Providers adapt vendor wire formats to/from these
types at their boundary; the agent core only ever sees these shapes.
"""

from dataclasses import dataclass, field
from typing import Literal

type Role = Literal["system", "user", "assistant", "tool"]
type ToolName = str


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A request from the assistant to invoke a tool.

    `arguments` is the raw JSON string emitted by the provider — deserialization
    happens at the tool dispatch boundary, not here. This keeps the type faithful
    to the wire shape and lets us round-trip through transcripts trivially.
    """

    id: str
    name: ToolName
    arguments: str


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of running a tool, fed back to the assistant as a tool-role message.

    `is_error=True` means the tool reported a failure (file not found, non-zero exit,
    etc.) — this is still normal LLM input. System failures raise instead.
    """

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class Message:
    """One entry in the conversation log.

    Fields beyond `role`/`content` are role-specific:
    - assistant messages may carry `tool_calls`
    - tool messages carry `tool_call_id` and put the tool output in `content`
    """

    role: Role
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True, slots=True)
class Turn:
    """A user input plus every assistant/tool message produced in response.

    Derived from the agent's event log; consumed by the TUI as a transcript group.
    """

    messages: tuple[Message, ...] = field(default_factory=tuple)
