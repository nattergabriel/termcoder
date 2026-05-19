"""Terminal REPL."""

import asyncio
import contextlib
import json
import signal
from collections.abc import Iterator, Sequence
from typing import Literal

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.input import Input
from prompt_toolkit.output import Output
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
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


class Repl:
    """Interactive terminal session."""

    _LiveMode = Literal["waiting", "assistant"]

    def __init__(
        self,
        *,
        console: Console | None = None,
        input: Input | None = None,
        output: Output | None = None,
    ) -> None:
        self._console = console or Console()
        self._session: PromptSession[str] = PromptSession(input=input, output=output)
        self._live: Live | None = None
        self._live_mode: Repl._LiveMode | None = None
        self._buffer = ""
        self._banner_rendered = False
        self._tool_calls: dict[str, ToolCall] = {}

    async def confirm_tool(self, call: ToolCall) -> PermissionDecision:
        """Prompt for a tool-call permission decision."""
        self._close_live()
        # Keep y/n answers out of the main prompt history.
        real_history = self._session.history
        self._session.history = InMemoryHistory()
        try:
            # Preserve the SIGINT handler installed for turn cancellation.
            line = await self._session.prompt_async(
                self._permission_prompt(call),
                handle_sigint=False,
            )
        except (KeyboardInterrupt, EOFError):
            raise asyncio.CancelledError from None
        finally:
            self._session.history = real_history
        return "allow" if line.strip().lower() in {"y", "yes"} else "deny"

    async def run(self, agent: Agent, slash_commands: SlashCommands) -> None:
        """Run until EOF."""
        self._render_banner(slash_commands.names())
        while True:
            try:
                user_input = await self._session.prompt_async("you > ")
            except EOFError:
                return
            except KeyboardInterrupt:
                continue

            if not user_input.strip():
                continue

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
            self._start_waiting()
            async for event in agent.run_turn(user_input):
                self._render(event)
        finally:
            self._close_live()
            self._tool_calls.clear()

    def _render(self, event: AgentEvent) -> None:
        match event:
            case TextDelta():
                self._append_text(event.text)
            case ToolCallRequested():
                self._close_live(spacing_after_assistant=True)
                self._tool_calls[event.tool_call.id] = event.tool_call
                self._console.print(self._tool_request_text(event.tool_call))
            case ToolCallStarted():
                self._close_live()
                self._start_waiting("running tool")
            case ToolCallCompleted():
                self._close_live()
                call = self._tool_calls.pop(event.result.tool_call_id, None)
                self._console.print(
                    self._tool_result_text(
                        self._tool_result_heading(call, event.result),
                        event.result.content,
                        "red" if event.result.is_error else "green",
                        preserve_tail=event.result.is_error,
                    )
                )
                self._print_blank_line()
                self._start_waiting()
            case TurnComplete():
                self._close_live(spacing_after_assistant=True)

    def _append_text(self, chunk: str) -> None:
        if not chunk:
            return
        if self._live_mode == "waiting":
            self._close_live()
        self._buffer += chunk
        if self._live is None:
            self._live = Live(
                self._assistant_text(self._buffer),
                console=self._console,
                refresh_per_second=20,
                transient=False,
            )
            self._live_mode = "assistant"
            self._live.start()
        else:
            self._live.update(self._assistant_text(self._buffer))

    def _close_live(self, *, spacing_after_assistant: bool = False) -> None:
        if self._live is None:
            return
        if spacing_after_assistant and self._live_mode == "assistant":
            rendered = self._assistant_text(self._buffer)
            rendered.append("\n")
            self._live.update(rendered)
        self._live.stop()
        self._live = None
        self._live_mode = None
        self._buffer = ""

    def _start_waiting(self, label: str = "thinking") -> None:
        if self._live is not None:
            return
        self._live = Live(
            Spinner("dots", text=Text(label, style="dim")),
            console=self._console,
            refresh_per_second=12,
            transient=True,
        )
        self._live_mode = "waiting"
        self._live.start()

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

    def _assistant_text(self, content: str) -> Text:
        return Text(self._prefix_lines(content, first="* ", rest="  "))

    def _tool_request_text(self, call: ToolCall) -> Text:
        text = Text()
        text.append("● ", style="green")
        text.append(self._tool_summary(call), style="bold")
        return text

    def _permission_prompt(self, call: ToolCall) -> str:
        return f"  └ Allow {self._tool_summary(call)}? [y/N] "

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
            return "Tool failed"
        if call is not None and call.name == "read":
            count = len(result.content.splitlines())
            return f"Read {self._pluralize(count, 'line')}"
        return "Tool completed"

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

    def _single_line_preview(self, content: str, *, max_length: int = 120) -> str:
        preview = " ".join(content.splitlines()).strip()
        if len(preview) <= max_length:
            return preview
        return preview[: max_length - 3] + "..."

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
