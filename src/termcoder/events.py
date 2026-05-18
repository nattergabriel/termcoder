"""Streaming events emitted during a turn."""

from dataclasses import dataclass

from termcoder.models import ToolCall, ToolResult


@dataclass(frozen=True, slots=True)
class TextDelta:
    """A chunk of assistant text from the provider stream."""

    text: str


@dataclass(frozen=True, slots=True)
class ToolCallRequested:
    """The assistant requested a tool call."""

    tool_call: ToolCall


@dataclass(frozen=True, slots=True)
class ToolCallCompleted:
    """The loop ran the tool (or the user denied it) and has a result to feed back."""

    result: ToolResult


@dataclass(frozen=True, slots=True)
class TurnComplete:
    """The assistant returned a final response with no further tool calls pending."""


type AgentEvent = TextDelta | ToolCallRequested | ToolCallCompleted | TurnComplete
