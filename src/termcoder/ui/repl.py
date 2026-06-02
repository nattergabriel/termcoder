"""Minimal terminal REPL."""

from prompt_toolkit import PromptSession
from prompt_toolkit.input import Input
from prompt_toolkit.output import Output
from rich.console import Console

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
from termcoder.skills import SkillCatalog, inject_inline_skills


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

    async def confirm_tool(self, call: ToolCall) -> PermissionDecision:
        """Prompt for a tool-call permission decision."""
        self._console.print(f"tool permission requested: {call.name} {call.arguments}")
        try:
            answer = await self._session.prompt_async("allow tool? [y/N] ")
        except EOFError:
            return "deny"
        normalized = answer.strip().lower()
        if normalized in {"y", "yes"}:
            return "allow"
        return "deny"

    async def run(
        self,
        agent: Agent,
        slash_commands: SlashCommands,
        skills: SkillCatalog | None = None,
    ) -> None:
        """Run until EOF."""
        self._render_banner(slash_commands)
        while True:
            try:
                user_input = await self._session.prompt_async("you > ")
            except EOFError:
                return
            except KeyboardInterrupt:
                self._console.print("cancelled")
                continue

            if not user_input.strip():
                continue

            if _is_registered_slash_command(user_input, slash_commands):
                await self._run_slash(slash_commands, user_input)
                continue

            turn_input = (
                inject_inline_skills(user_input, skills) if skills is not None else user_input
            )
            if _is_slash_line(user_input) and turn_input == user_input:
                await self._run_slash(slash_commands, user_input)
                continue

            await self._run_turn(agent, turn_input)

    async def _run_slash(self, slash_commands: SlashCommands, line: str) -> None:
        try:
            message = await slash_commands.dispatch(line)
        except SlashCommandError as exc:
            self._console.print(f"command error: {exc}")
            return
        self._console.print(message)

    async def _run_turn(self, agent: Agent, user_input: str) -> None:
        async for event in agent.run_turn(user_input):
            self._render(event)

    def _render(self, event: AgentEvent) -> None:
        match event:
            case TextDelta():
                self._console.print(event.text, end="")
            case ToolCallRequested():
                self._console.print(
                    f"\ntool requested: {event.tool_call.name} {event.tool_call.arguments}"
                )
            case ToolCallStarted():
                self._console.print(f"tool started: {event.tool_call.name}")
            case ToolCallCompleted():
                self._console.print(f"tool result: {event.result.content}")
            case TurnComplete():
                self._console.print("")

    def _render_banner(self, slash_commands: SlashCommands) -> None:
        commands = ", ".join(f"/{name}" for name in slash_commands.names())
        if commands:
            self._console.print(f"termcoder ({commands})")
            return
        self._console.print("termcoder")


def _is_registered_slash_command(line: str, slash_commands: SlashCommands) -> bool:
    stripped = line.strip()
    if not stripped.startswith("/"):
        return False
    parts = stripped[1:].split(maxsplit=1)
    if not parts:
        return False
    name = parts[0]
    return name in slash_commands.names()


def _is_slash_line(line: str) -> bool:
    return line.strip().startswith("/")
