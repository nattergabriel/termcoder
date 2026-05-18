"""Terminal REPL."""

import asyncio
import contextlib
import signal
from collections.abc import Iterator

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.input import Input
from prompt_toolkit.output import Output
from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.text import Text

from termcoder.agent.loop import Agent
from termcoder.commands.registry import SlashCommandError, SlashCommands
from termcoder.events import (
    AgentEvent,
    TextDelta,
    ToolCallCompleted,
    ToolCallRequested,
    TurnComplete,
)
from termcoder.models import PermissionDecision, ToolCall


class Repl:
    """Interactive terminal session."""

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
        self._buffer = ""

    async def confirm_tool(self, call: ToolCall) -> PermissionDecision:
        """Prompt for a tool-call permission decision."""
        # Keep y/n answers out of the main prompt history.
        real_history = self._session.history
        self._session.history = InMemoryHistory()
        args_preview = (
            call.arguments if len(call.arguments) <= 120 else call.arguments[:117] + "..."
        )
        try:
            # Preserve the SIGINT handler installed for turn cancellation.
            line = await self._session.prompt_async(
                f"[permission] {call.name} {args_preview} — allow? [y/N] ",
                handle_sigint=False,
            )
        except (KeyboardInterrupt, EOFError):
            raise asyncio.CancelledError from None
        finally:
            self._session.history = real_history
        return "allow" if line.strip().lower() in {"y", "yes"} else "deny"

    async def run(self, agent: Agent, slash_commands: SlashCommands) -> None:
        """Run until EOF."""
        while True:
            try:
                user_input = await self._session.prompt_async("> ")
            except EOFError:
                return
            except KeyboardInterrupt:
                continue

            if not user_input.strip():
                continue

            if user_input.lstrip().startswith("/"):
                await self._run_slash(slash_commands, user_input)
                continue

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
            self._console.print(f"[red]{escape(str(exc))}[/red]")
        else:
            self._console.print(f"[dim]{escape(message)}[/dim]")

    async def _run_turn(self, agent: Agent, user_input: str) -> None:
        try:
            async for event in agent.run_turn(user_input):
                self._render(event)
        finally:
            self._close_live()

    def _render(self, event: AgentEvent) -> None:
        match event:
            case TextDelta():
                self._append_text(event.text)
            case ToolCallRequested():
                self._close_live()
                self._console.print(
                    f"[cyan]→ tool[/cyan] [bold]{escape(event.tool_call.name)}[/bold] "
                    f"{escape(event.tool_call.arguments)}"
                )
            case ToolCallCompleted():
                self._close_live()
                style = "red" if event.result.is_error else "green"
                label = "tool-error" if event.result.is_error else "tool-ok"
                self._console.print(f"[{style}]← {label}[/{style}] {escape(event.result.content)}")
            case TurnComplete():
                self._close_live()

    def _append_text(self, chunk: str) -> None:
        self._buffer += chunk
        if self._live is None:
            self._live = Live(
                Text(self._buffer),
                console=self._console,
                refresh_per_second=20,
                transient=False,
            )
            self._live.start()
        else:
            self._live.update(Text(self._buffer))

    def _close_live(self) -> None:
        if self._live is None:
            return
        self._live.stop()
        self._live = None
        self._buffer = ""

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
