"""Terminal REPL."""

import asyncio
import contextlib
import signal
from collections.abc import Iterator, Sequence

from prompt_toolkit import PromptSession
from prompt_toolkit.input import Input
from prompt_toolkit.output import Output
from rich.console import Console, RenderableType
from rich.live import Live

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
from termcoder.models import PermissionDecision, ToolCall
from termcoder.ui.choice import ChoiceReader
from termcoder.ui.formatting import permission_prompt
from termcoder.ui.history import PromptHistory
from termcoder.ui.interaction import ChoicePrompt, ChoicePromptState
from termcoder.ui.rendering import TurnRenderer
from termcoder.ui.turn import TurnState


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
        self._history = PromptHistory(self._session)
        self._prompt_key_bindings = self._history.key_bindings()
        self._choice_reader = ChoiceReader(self._session, self._refresh_live)
        self._renderer = TurnRenderer(self._console)
        self._turn = TurnState()
        self._live: Live | None = None
        self._banner_rendered = False
        self._choice_state: ChoicePromptState | None = None

    async def confirm_tool(self, call: ToolCall) -> PermissionDecision:
        """Prompt for a tool-call permission decision."""
        return await self.ask_choice(permission_prompt(call))

    async def ask_choice[T](self, prompt: ChoicePrompt[T]) -> T:
        """Ask a reusable arrow-key navigable question below the active turn."""
        state = prompt.initial_state()
        self._choice_state = state
        self._turn.waiting_label = None
        self._refresh_live()
        try:
            await self._choice_reader.read(state)
            return prompt.options[state.selected_index].value
        finally:
            self._choice_state = None
            if self._turn.items or self._turn.waiting_label is not None:
                self._refresh_live()
            else:
                self._close_live()

    async def run(self, agent: Agent, slash_commands: SlashCommands) -> None:
        """Run until EOF."""
        self._render_banner(slash_commands.names())
        while True:
            try:
                self._history.reset_navigation()
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

            self._history.append(user_input)
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
            self._console.print(self._renderer.status_text("command error", str(exc), "red"))
        else:
            self._console.print(self._renderer.status_text("command", message, "bright_black"))

    async def _run_turn(self, agent: Agent, user_input: str) -> None:
        try:
            self._begin_turn()
            async for event in agent.run_turn(user_input):
                self._render(event)
        finally:
            self._choice_state = None
            self._close_live()
            self._turn.clear()

    def _render(self, event: AgentEvent) -> None:
        match event:
            case TextDelta():
                if self._turn.append_text(event.text):
                    self._refresh_live()
            case ToolCallRequested():
                self._turn.request_tool(event.tool_call)
                self._refresh_live()
            case ToolCallStarted():
                self._turn.start_tool(event.tool_call)
                self._refresh_live()
            case ToolCallCompleted():
                self._turn.complete_tool(event.result)
                self._refresh_live()
            case TurnComplete():
                self._turn.waiting_label = None
                self._close_live()

    def _begin_turn(self) -> None:
        self._choice_state = None
        self._turn.begin()
        self._refresh_live()

    def _close_live(self) -> None:
        if self._live is None:
            return
        self._live.update(self._turn_renderable())
        self._live.stop()
        self._live = None
        self._print_blank_line()

    def _refresh_live(self) -> None:
        renderable = self._turn_renderable()
        if self._live is None:
            self._live = Live(
                renderable,
                console=self._console,
                refresh_per_second=20,
                transient=False,
                vertical_overflow="visible",
            )
            self._live.start()
            return
        self._live.update(renderable)

    def _turn_renderable(self) -> RenderableType:
        return self._renderer.render(self._turn, self._choice_state)

    def _render_banner(self, command_names: Sequence[str] = ()) -> None:
        if self._banner_rendered:
            return
        self._console.print(self._renderer.banner(command_names))
        self._print_blank_line()
        self._banner_rendered = True

    def _print_blank_line(self) -> None:
        self._console.print("")

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
