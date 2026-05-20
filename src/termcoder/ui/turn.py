"""In-memory state for one assistant turn."""

from dataclasses import dataclass
from typing import Literal

from termcoder.events import TextDelta, ToolCallCompleted, ToolCallRequested, ToolCallStarted
from termcoder.models import ToolCall, ToolResult


@dataclass(slots=True)
class AssistantView:
    content: str


@dataclass(slots=True)
class ToolView:
    call: ToolCall
    status: Literal["requested", "running", "completed"]
    result: ToolResult | None = None


@dataclass(slots=True)
class ResultView:
    result: ToolResult


type TurnItem = AssistantView | ToolView | ResultView


class TurnState:
    """Mutable display state for the active turn."""

    def __init__(self) -> None:
        self.tool_calls: dict[str, ToolCall] = {}
        self.tool_views: dict[str, ToolView] = {}
        self.items: list[TurnItem] = []
        self.waiting_label: str | None = None

    def begin(self) -> None:
        self.clear()
        self.waiting_label = "thinking"

    def clear(self) -> None:
        self.tool_calls.clear()
        self.tool_views.clear()
        self.items.clear()
        self.waiting_label = None

    def append_text(self, chunk: str) -> bool:
        if not chunk:
            return False
        self.waiting_label = None
        if self.items and isinstance(self.items[-1], AssistantView):
            self.items[-1].content += chunk
        else:
            self.items.append(AssistantView(content=chunk))
        return True

    def request_tool(self, event: ToolCallRequested) -> None:
        self.waiting_label = None
        view = ToolView(call=event.tool_call, status="requested")
        self.tool_calls[event.tool_call.id] = event.tool_call
        self.tool_views[event.tool_call.id] = view
        self.items.append(view)

    def start_tool(self, event: ToolCallStarted) -> None:
        self.waiting_label = "running tool"
        view = self.tool_views.get(event.tool_call.id)
        if view is None:
            view = ToolView(call=event.tool_call, status="running")
            self.tool_views[event.tool_call.id] = view
            self.items.append(view)
            return
        view.status = "running"

    def complete_tool(self, event: ToolCallCompleted) -> None:
        self.waiting_label = "thinking"
        self.tool_calls.pop(event.result.tool_call_id, None)
        view = self.tool_views.get(event.result.tool_call_id)
        if view is None:
            self.items.append(ResultView(result=event.result))
            return
        view.status = "completed"
        view.result = event.result

    def apply_text_delta(self, event: TextDelta) -> bool:
        return self.append_text(event.text)
