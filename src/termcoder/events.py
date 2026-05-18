"""Streaming output of the agent loop, consumed by the TUI as an async iterator.

The provider yields `TextDelta` and `ToolCallRequested` as it streams; the loop adds
`ToolCallResult` after running the tool, and `TurnComplete` when the round ends.
System errors are raised through the async generator, not yielded as events.
"""

from dataclasses import dataclass

from termcoder.models import ToolCall, ToolResult


@dataclass(frozen=True, slots=True)
class TextDelta:
    """A chunk of assistant text from the provider stream."""

    text: str


@dataclass(frozen=True, slots=True)
class ToolCallRequested:
    """The assistant has finished requesting a tool call (arguments fully streamed)."""

    tool_call: ToolCall


@dataclass(frozen=True, slots=True)
class ToolCallCompleted:
    """The loop ran the tool (or the user denied it) and has a result to feed back."""

    result: ToolResult


@dataclass(frozen=True, slots=True)
class TurnComplete:
    """The assistant returned a final response with no further tool calls pending."""


type AgentEvent = TextDelta | ToolCallRequested | ToolCallCompleted | TurnComplete
