"""In-memory state for one assistant turn."""

from dataclasses import dataclass

from termcoder.models import ToolCall, ToolResult


@dataclass(slots=True)
class AssistantView:
    content: str


@dataclass(slots=True)
class ToolView:
    call: ToolCall
    is_running: bool = False
    result: ToolResult | None = None


@dataclass(slots=True)
class ResultView:
    result: ToolResult


type TurnItem = AssistantView | ToolView | ResultView


class TurnState:
    """Mutable display state for the active turn."""

    def __init__(self) -> None:
        self.tool_views: dict[str, ToolView] = {}
        self.items: list[TurnItem] = []
        self.waiting_label: str | None = None

    def begin(self) -> None:
        self.clear()
        self.waiting_label = "thinking"

    def clear(self) -> None:
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

    def request_tool(self, call: ToolCall) -> None:
        self.waiting_label = None
        view = ToolView(call=call)
        self.tool_views[call.id] = view
        self.items.append(view)

    def start_tool(self, call: ToolCall) -> None:
        self.waiting_label = "running tool"
        view = self.tool_views.get(call.id)
        if view is None:
            view = ToolView(call=call, is_running=True)
            self.tool_views[call.id] = view
            self.items.append(view)
            return
        view.is_running = True

    def complete_tool(self, result: ToolResult) -> None:
        self.waiting_label = "thinking"
        view = self.tool_views.get(result.tool_call_id)
        if view is None:
            self.items.append(ResultView(result=result))
            return
        view.is_running = False
        view.result = result
