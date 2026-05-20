"""Rich renderers for terminal UI state."""

from collections.abc import Sequence

from rich.console import Console, Group, RenderableType
from rich.spinner import Spinner
from rich.text import Text

from termcoder.ui.formatting import (
    line_preview,
    prefix_lines,
    slash_command_summary,
    tool_result_label,
    tool_summary,
)
from termcoder.ui.interaction import ChoicePromptState
from termcoder.ui.turn import AssistantView, ResultView, ToolView, TurnState

_CHOICE_SEPARATOR_MAX_WIDTH = 80


class TurnRenderer:
    """Render a turn and any inline prompt into Rich objects."""

    def __init__(self, console: Console) -> None:
        self._console = console

    def render(
        self,
        turn: TurnState,
        choice_prompt: ChoicePromptState | None,
    ) -> RenderableType:
        renderables: list[RenderableType] = []
        for item in turn.items:
            if renderables:
                renderables.append(Text(""))
            match item:
                case AssistantView():
                    renderables.append(self.assistant_text(item.content))
                case ToolView():
                    renderables.append(self.tool_view_text(item))
                case ResultView():
                    renderables.append(
                        self.tool_result_text(
                            tool_result_label(None, item.result),
                            item.result.content,
                            "red" if item.result.is_error else "green",
                            preserve_tail=item.result.is_error,
                        )
                    )
        if turn.waiting_label is not None:
            if renderables:
                renderables.append(Text(""))
            renderables.append(Spinner("dots", text=Text(turn.waiting_label, style="dim")))
        if choice_prompt is not None:
            if renderables:
                renderables.append(Text(""))
            renderables.append(self.choice_prompt_text(choice_prompt))
        if not renderables:
            return Text("")
        return Group(*renderables)

    def banner(self, command_names: Sequence[str]) -> Text:
        banner = Text()
        banner.append("termcoder", style="bold cyan")
        banner.append("  ")
        banner.append("TUI coding agent", style="bright_black")
        banner.append("\n")
        banner.append("Ctrl-D exits | Ctrl-C cancels a turn", style="dim")
        if command_names:
            banner.append("\n")
            banner.append(slash_command_summary(tuple(command_names)), style="dim")
        return banner

    def choice_prompt_text(self, state: ChoicePromptState) -> Text:
        text = Text()
        text.append(
            "─" * min(self._console.width, _CHOICE_SEPARATOR_MAX_WIDTH),
            style="bright_black",
        )
        text.append("\n")
        text.append(state.prompt.title)
        text.append("\n")
        for index, option in enumerate(state.prompt.options):
            selected = index == state.selected_index
            marker = "› " if selected else "  "
            style = "bold bright_blue" if selected else ""
            text.append(marker, style="bright_blue" if selected else "bright_black")
            text.append(f"{index + 1}. {option.label}", style=style)
            if option.description is not None:
                text.append(f" {option.description}", style="dim")
            text.append("\n")
        text.append(state.prompt.footer, style="dim")
        return text

    def assistant_text(self, content: str) -> Text:
        return Text(prefix_lines(content, first="* ", rest="  "))

    def tool_view_text(self, view: ToolView) -> Text:
        text = Text()
        text.append("● ", style=self.tool_status_style(view))
        text.append(tool_summary(view.call), style="bold")
        if view.result is not None:
            text.append("\n")
            text.append(
                self.tool_result_text(
                    tool_result_label(view.call, view.result),
                    view.result.content,
                    "red" if view.result.is_error else "bright_black",
                    preserve_tail=view.result.is_error,
                )
            )
        elif view.is_running:
            text.append("\n")
            text.append("  └ Running", style="bright_black")
        return text

    def tool_status_style(self, view: ToolView) -> str:
        if view.result is None:
            return "bright_black"
        return "red" if view.result.is_error else "green"

    def tool_result_text(
        self,
        label: str,
        content: str,
        style: str,
        *,
        preserve_tail: bool = False,
    ) -> Text:
        text = Text()
        text.append("  └ ", style="bright_black")
        text.append(label, style=style)
        preview = line_preview(content, max_lines=5, preserve_tail=preserve_tail)
        if preview:
            text.append("\n")
            text.append(prefix_lines(preview, first="    ", rest="    "), style="bright_black")
        return text

    def status_text(self, label: str, content: str, style: str) -> Text:
        text = Text()
        text.append(f"* {label}: ", style=style)
        text.append(content)
        return text
