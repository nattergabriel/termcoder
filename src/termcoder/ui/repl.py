"""Terminal REPL."""

import asyncio
import contextlib
import json
import signal
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal, TypeVar, cast

from prompt_toolkit import PromptSession
from prompt_toolkit.input import Input
from prompt_toolkit.input.typeahead import get_typeahead, store_typeahead
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPress, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.output import Output
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.text import Text

from termcoder.agent.loop import Agent
from termcoder.commands.registry import SlashCommandError, SlashCommands
from termcoder.events import (
    AgentEvent,
    TextDelta,
    ToolCallCompleted,
    ToolCallRequested,
    ToolCallStarted,
    TurnComplete,
)
from termcoder.models import PermissionDecision, ToolCall, ToolResult
from termcoder.ui.interaction import ChoiceOption, ChoicePrompt

T = TypeVar("T")


@dataclass(slots=True)
class _AssistantView:
    content: str


@dataclass(slots=True)
class _ToolView:
    call: ToolCall
    status: Literal["requested", "running", "completed"]
    result: ToolResult | None = None


@dataclass(slots=True)
class _ResultView:
    result: ToolResult


@dataclass(slots=True)
class _ChoicePromptState:
    prompt: ChoicePrompt[object]
    selected_index: int


type _TurnItem = _AssistantView | _ToolView | _ResultView


class Repl:
    """Interactive terminal session."""

    _LiveMode = Literal["turn"]

    def __init__(
        self,
        *,
        console: Console | None = None,
        input: Input | None = None,
        output: Output | None = None,
    ) -> None:
        self._console = console or Console()
        self._session: PromptSession[str] = PromptSession(input=input, output=output)
        self._prompt_key_bindings = self._main_prompt_key_bindings()
        self._live: Live | None = None
        self._live_mode: Repl._LiveMode | None = None
        self._banner_rendered = False
        self._tool_calls: dict[str, ToolCall] = {}
        self._tool_views: dict[str, _ToolView] = {}
        self._turn_items: list[_TurnItem] = []
        self._waiting_label: str | None = None
        self._choice_prompt: _ChoicePromptState | None = None
        self._input_history: list[str] = []
        self._history_index: int | None = None

    async def confirm_tool(self, call: ToolCall) -> PermissionDecision:
        """Prompt for a tool-call permission decision."""
        return await self.ask_choice(self._permission_prompt(call))

    async def ask_choice(self, prompt: ChoicePrompt[T]) -> T:
        """Ask a reusable arrow-key navigable question below the active turn."""
        if not prompt.options:
            raise ValueError("choice prompt requires at least one option")
        if not 0 <= prompt.default_index < len(prompt.options):
            raise ValueError("choice prompt default_index is out of range")

        state = _ChoicePromptState(
            prompt=cast(ChoicePrompt[object], prompt),
            selected_index=prompt.default_index,
        )
        self._choice_prompt = state
        self._waiting_label = None
        self._refresh_live()
        try:
            await self._read_choice(state)
            return prompt.options[state.selected_index].value
        finally:
            self._choice_prompt = None
            if self._turn_items or self._waiting_label is not None:
                self._refresh_live()
            else:
                self._close_live()

    async def run(self, agent: Agent, slash_commands: SlashCommands) -> None:
        """Run until EOF."""
        self._render_banner(slash_commands.names())
        while True:
            try:
                self._history_index = None
                user_input = await self._session.prompt_async(
                    "you > ",
                    key_bindings=self._prompt_key_bindings,
                )
            except EOFError:
                return
            except KeyboardInterrupt:
                continue

            if not user_input.strip():
                continue

            self._input_history.append(user_input)
            if user_input.lstrip().startswith("/"):
                await self._run_slash(slash_commands, user_input)
                continue

            self._print_blank_line()
            turn = asyncio.create_task(self._run_turn(agent, user_input))
            try:
                with self._cancel_on_sigint(turn):
                    await turn
            except asyncio.CancelledError:
                self._close_live()
                self._console.print("[dim]turn cancelled[/dim]")

    async def _run_slash(self, slash_commands: SlashCommands, line: str) -> None:
        try:
            message = await slash_commands.dispatch(line)
        except SlashCommandError as exc:
            self._console.print(self._status_text("command error", str(exc), "red"))
        else:
            self._console.print(self._status_text("command", message, "bright_black"))

    async def _run_turn(self, agent: Agent, user_input: str) -> None:
        try:
            self._begin_turn()
            async for event in agent.run_turn(user_input):
                self._render(event)
        finally:
            self._choice_prompt = None
            self._waiting_label = None
            self._close_live()
            self._tool_calls.clear()
            self._tool_views.clear()
            self._turn_items.clear()

    def _render(self, event: AgentEvent) -> None:
        match event:
            case TextDelta():
                self._append_text(event.text)
            case ToolCallRequested():
                self._waiting_label = None
                requested_view = _ToolView(call=event.tool_call, status="requested")
                self._tool_calls[event.tool_call.id] = event.tool_call
                self._tool_views[event.tool_call.id] = requested_view
                self._turn_items.append(requested_view)
                self._refresh_live()
            case ToolCallStarted():
                self._waiting_label = "running tool"
                started_view = self._tool_views.get(event.tool_call.id)
                if started_view is None:
                    started_view = _ToolView(call=event.tool_call, status="running")
                    self._tool_views[event.tool_call.id] = started_view
                    self._turn_items.append(started_view)
                else:
                    started_view.status = "running"
                self._refresh_live()
            case ToolCallCompleted():
                self._waiting_label = "thinking"
                self._tool_calls.pop(event.result.tool_call_id, None)
                completed_view = self._tool_views.get(event.result.tool_call_id)
                if completed_view is None:
                    self._turn_items.append(_ResultView(result=event.result))
                else:
                    completed_view.status = "completed"
                    completed_view.result = event.result
                self._refresh_live()
            case TurnComplete():
                self._waiting_label = None
                self._close_live()

    def _append_text(self, chunk: str) -> None:
        if not chunk:
            return
        self._waiting_label = None
        if self._turn_items and isinstance(self._turn_items[-1], _AssistantView):
            self._turn_items[-1].content += chunk
        else:
            self._turn_items.append(_AssistantView(content=chunk))
        self._refresh_live()

    def _begin_turn(self) -> None:
        self._tool_calls.clear()
        self._tool_views.clear()
        self._turn_items.clear()
        self._choice_prompt = None
        self._waiting_label = "thinking"
        self._refresh_live()

    def _close_live(self) -> None:
        if self._live is None:
            return
        self._live.update(self._turn_renderable())
        self._live.stop()
        self._live = None
        self._live_mode = None
        self._print_blank_line()

    def _start_waiting(self, label: str = "thinking") -> None:
        self._waiting_label = label
        self._refresh_live()

    def _refresh_live(self) -> None:
        renderable = self._turn_renderable()
        if self._live is None:
            self._live = Live(
                renderable,
                console=self._console,
                refresh_per_second=20,
                transient=False,
            )
            self._live_mode = "turn"
            self._live.start()
            return
        self._live.update(renderable)

    def _turn_renderable(self) -> RenderableType:
        renderables: list[RenderableType] = []
        for item in self._turn_items:
            if renderables:
                renderables.append(Text(""))
            match item:
                case _AssistantView():
                    renderables.append(self._assistant_text(item.content))
                case _ToolView():
                    renderables.append(self._tool_view_text(item))
                case _ResultView():
                    renderables.append(
                        self._tool_result_text(
                            self._tool_result_heading(None, item.result),
                            item.result.content,
                            "red" if item.result.is_error else "green",
                            preserve_tail=item.result.is_error,
                        )
                    )
        if self._waiting_label is not None:
            if renderables:
                renderables.append(Text(""))
            renderables.append(Text(self._waiting_label, style="dim"))
        if self._choice_prompt is not None:
            if renderables:
                renderables.append(Text(""))
            renderables.append(self._choice_prompt_text(self._choice_prompt))
        if not renderables:
            return Text("")
        return Group(*renderables)

    def _render_banner(self, command_names: Sequence[str] = ()) -> None:
        if self._banner_rendered:
            return
        banner = Text()
        banner.append("termcoder", style="bold cyan")
        banner.append("  ")
        banner.append("TUI coding agent", style="bright_black")
        banner.append("\n")
        banner.append("Ctrl-D exits | Ctrl-C cancels a turn", style="dim")
        if command_names:
            banner.append("\n")
            banner.append(self._slash_command_summary(command_names), style="dim")
        self._console.print(banner)
        self._print_blank_line()
        self._banner_rendered = True

    def _main_prompt_key_bindings(self) -> KeyBindings:
        bindings = KeyBindings()

        @bindings.add("up")
        def history_previous(event: KeyPressEvent) -> None:
            del event
            self._history_previous()

        @bindings.add("down")
        def history_next(event: KeyPressEvent) -> None:
            del event
            self._history_next()

        return bindings

    def _history_previous(self) -> None:
        if not self._input_history:
            return
        if self._history_index is None:
            self._history_index = len(self._input_history) - 1
        else:
            self._history_index = max(0, self._history_index - 1)
        self._set_prompt_text(self._input_history[self._history_index])

    def _history_next(self) -> None:
        if self._history_index is None:
            return
        if self._history_index >= len(self._input_history) - 1:
            self._history_index = None
            self._set_prompt_text("")
            return
        self._history_index += 1
        self._set_prompt_text(self._input_history[self._history_index])

    def _set_prompt_text(self, text: str) -> None:
        buffer = self._session.default_buffer
        buffer.text = text
        buffer.cursor_position = len(text)

    async def _read_choice(self, state: _ChoicePromptState) -> None:
        queue: asyncio.Queue[KeyPress] = asyncio.Queue()
        prompt_input = self._session.input

        def input_ready() -> None:
            for key_press in prompt_input.read_keys():
                queue.put_nowait(key_press)

        for key_press in get_typeahead(prompt_input):
            queue.put_nowait(key_press)
        with prompt_input.raw_mode(), prompt_input.attach(input_ready):
            input_ready()
            while True:
                key_press = await queue.get()
                if self._apply_choice_key(state, key_press):
                    self._store_choice_leftovers(prompt_input, queue)
                    return

    def _store_choice_leftovers(
        self,
        prompt_input: Input,
        queue: asyncio.Queue[KeyPress],
    ) -> None:
        leftovers: list[KeyPress] = []
        while not queue.empty():
            leftovers.append(queue.get_nowait())
        if leftovers:
            store_typeahead(prompt_input, leftovers)

    def _apply_choice_key(self, state: _ChoicePromptState, key_press: KeyPress) -> bool:
        key = key_press.key
        if key in {Keys.ControlC, Keys.ControlD, Keys.Escape}:
            raise asyncio.CancelledError
        if key in {Keys.Up, Keys.ControlP, Keys.BackTab}:
            self._move_choice(state, -1)
            return False
        if key in {Keys.Down, Keys.ControlN, Keys.ControlI}:
            self._move_choice(state, 1)
            return False
        if key in {Keys.ControlJ, Keys.ControlM}:
            return True
        if isinstance(key, str):
            self._select_choice_shortcut(state, key.lower())
        return False

    def _select_choice_shortcut(self, state: _ChoicePromptState, key: str) -> None:
        for index, option in enumerate(state.prompt.options):
            if option.shortcut is not None and option.shortcut.lower() == key:
                state.selected_index = index
                self._refresh_live()
                return
            if str(index + 1) == key:
                state.selected_index = index
                self._refresh_live()
                return

    def _move_choice(self, state: _ChoicePromptState, offset: int) -> None:
        state.selected_index = (state.selected_index + offset) % len(state.prompt.options)
        self._refresh_live()

    def _choice_prompt_text(self, state: _ChoicePromptState) -> Text:
        text = Text()
        text.append("─" * min(self._console.width, 88), style="bright_black")
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

    def _assistant_text(self, content: str) -> Text:
        return Text(self._prefix_lines(content, first="* ", rest="  "))

    def _tool_request_text(self, call: ToolCall) -> Text:
        text = Text()
        text.append("● ", style="green")
        text.append(self._tool_summary(call), style="bold")
        return text

    def _tool_view_text(self, view: _ToolView) -> Text:
        text = Text()
        text.append("● ", style=self._tool_status_style(view))
        text.append(self._tool_summary(view.call), style="bold")
        if view.result is not None:
            text.append("\n")
            text.append(
                self._tool_result_text(
                    self._tool_result_label(view.call, view.result),
                    view.result.content,
                    "red" if view.result.is_error else "bright_black",
                    preserve_tail=view.result.is_error,
                )
            )
        elif view.status == "running":
            text.append("\n")
            text.append("  └ Running", style="bright_black")
        return text

    def _tool_status_style(self, view: _ToolView) -> str:
        if view.result is None:
            return "bright_black"
        return "red" if view.result.is_error else "green"

    def _permission_prompt(self, call: ToolCall) -> ChoicePrompt[PermissionDecision]:
        return ChoicePrompt(
            title=f"Allow {self._tool_summary(call)}?",
            options=(
                ChoiceOption(label="Yes", value="allow", shortcut="y"),
                ChoiceOption(label="No", value="deny", shortcut="n"),
            ),
            default_index=1,
        )

    def _tool_result_text(
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
        preview = self._line_preview(content, max_lines=5, preserve_tail=preserve_tail)
        if preview:
            text.append("\n")
            text.append(
                self._prefix_lines(preview, first="    ", rest="    "), style="bright_black"
            )
        return text

    def _status_text(self, label: str, content: str, style: str) -> Text:
        text = Text()
        text.append(f"* {label}: ", style=style)
        text.append(content)
        return text

    def _print_blank_line(self) -> None:
        self._console.print("")

    def _tool_result_heading(self, call: ToolCall | None, result: ToolResult) -> str:
        label = self._tool_result_label(call, result)
        if call is None:
            return label
        return f"{self._tool_summary(call)}: {label}"

    def _tool_result_label(self, call: ToolCall | None, result: ToolResult) -> str:
        if result.is_error:
            if "denied permission" in result.content.lower():
                return "Denied"
            return "Failed"
        if call is not None and call.name == "read":
            count = len(result.content.splitlines())
            return f"Read {self._pluralize(count, 'line')}"
        return "Done"

    def _tool_summary(self, call: ToolCall) -> str:
        summary = self._tool_display_name(call.name)
        preview = self._argument_preview(call.arguments)
        if not preview:
            return summary
        return f"{summary}({preview})"

    def _tool_display_name(self, name: str) -> str:
        return name.replace("_", " ").title().replace(" ", "")

    def _argument_preview(self, arguments: str) -> str:
        try:
            parsed: object = json.loads(arguments)
        except json.JSONDecodeError:
            return self._single_line_preview(arguments)

        if not isinstance(parsed, dict):
            return self._single_line_preview(arguments)

        command = parsed.get("command")
        if isinstance(command, str):
            return self._single_line_preview(command)

        path = parsed.get("path")
        if isinstance(path, str):
            content = parsed.get("content")
            if isinstance(content, str):
                return self._single_line_preview(f"{path}, {self._character_count(content)}")
            return self._single_line_preview(path)

        return self._single_line_preview(arguments)

    def _single_line_preview(self, content: str) -> str:
        preview = " ".join(content.splitlines()).strip()
        if len(preview) <= 120:
            return preview
        return preview[:117] + "..."

    def _line_preview(self, content: str, *, max_lines: int, preserve_tail: bool = False) -> str:
        lines = content.splitlines()
        if len(lines) <= max_lines:
            return content
        hidden = len(lines) - max_lines
        if preserve_tail and max_lines >= 3:
            head_count = max_lines - 2
            hidden = len(lines) - head_count - 1
            return "\n".join([*lines[:head_count], self._hidden_line(hidden), lines[-1]])
        return "\n".join([*lines[:max_lines], self._hidden_line(hidden)])

    def _slash_command_summary(self, command_names: Sequence[str]) -> str:
        return " ".join(f"/{name}" for name in command_names)

    def _character_count(self, content: str) -> str:
        return self._pluralize(len(content), "character")

    def _hidden_line(self, count: int) -> str:
        noun = "line" if count == 1 else "lines"
        return f"... {count} more {noun}"

    def _pluralize(self, count: int, noun: str) -> str:
        suffix = "" if count == 1 else "s"
        return f"{count} {noun}{suffix}"

    def _prefix_lines(self, content: str, *, first: str, rest: str) -> str:
        lines = content.splitlines(keepends=True)
        if not lines:
            return first
        prefixed = []
        for index, line in enumerate(lines):
            prefix = first if index == 0 else rest
            prefixed.append(prefix + line)
        return "".join(prefixed)

    @contextlib.contextmanager
    def _cancel_on_sigint(self, task: asyncio.Task[None]) -> Iterator[None]:
        loop = asyncio.get_running_loop()

        def cancel_task() -> None:
            if not task.done():
                task.cancel()

        try:
            loop.add_signal_handler(signal.SIGINT, cancel_task)
        except NotImplementedError:
            yield
            return

        try:
            yield
        finally:
            with contextlib.suppress(NotImplementedError):
                loop.remove_signal_handler(signal.SIGINT)
