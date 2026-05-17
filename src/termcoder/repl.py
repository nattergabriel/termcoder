"""TUI: rich-rendered streaming output + prompt_toolkit input.

The only module that imports `rich` or `prompt_toolkit`. `Repl` owns a single
`Console` and a single `PromptSession`; it exposes `confirm_tool` (wired in via
composition as the permission prompt) and `run(agent)` (the session loop).

Rendering: assistant `TextDelta`s stream into a `rich.live.Live` block that
re-renders in place as each chunk arrives. The Live closes on any non-text
event so tool-call lines and the permission prompt can use the cursor cleanly,
then reopens on the next `TextDelta`. Tool calls and results render as styled
single lines.

Cancellation: at the prompt, prompt_toolkit raises `KeyboardInterrupt` on
Ctrl-C — we catch it and re-prompt. Mid-turn, a SIGINT handler cancels the
running task; the agent loop catches `CancelledError` and rolls back state.
Ctrl-D raises `EOFError`, which exits the session.
"""

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
from termcoder.events import (
    AgentEvent,
    TextDelta,
    ToolCallCompleted,
    ToolCallRequested,
    TurnComplete,
)
from termcoder.types import PermissionDecision, ToolCall


class Repl:
    """rich + prompt_toolkit session driving the agent loop."""

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
        """Inline `[y/N]` permission prompt — wired in as the `prompt_user` callable."""
        # Throwaway history so y/n answers don't pollute the main prompt's Up-arrow recall.
        real_history = self._session.history
        self._session.history = InMemoryHistory()
        try:
            line = await self._session.prompt_async(
                f"[permission] {call.name} {call.arguments} — allow? [y/N] "
            )
        except (KeyboardInterrupt, EOFError):
            return "deny"
        finally:
            self._session.history = real_history
        return "allow" if line.strip().lower() in {"y", "yes"} else "deny"

    async def run(self, agent: Agent) -> None:
        """Read input, drive a turn, render its events, repeat until EOF."""
        while True:
            try:
                user_input = await self._session.prompt_async("> ")
            except EOFError:
                return
            except KeyboardInterrupt:
                continue

            if not user_input.strip():
                continue

            turn = asyncio.create_task(self._run_turn(agent, user_input))
            try:
                with self._cancel_on_sigint(turn):
                    await turn
            except asyncio.CancelledError:
                self._close_live()
                self._console.print("[dim]turn cancelled[/dim]")

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
