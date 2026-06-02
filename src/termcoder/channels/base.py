"""Shared behavior for text-oriented channels."""

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
from termcoder.skills import SkillCatalog, inject_inline_skills


class BaseChannel:
    """Reusable slash-command, skill-injection, and event-rendering flow."""

    async def handle_user_input(
        self,
        agent: Agent,
        slash_commands: SlashCommands,
        line: str,
        skills: SkillCatalog | None = None,
    ) -> None:
        """Handle one user message."""
        if not line.strip():
            return

        if _is_registered_slash_command(line, slash_commands):
            await self._run_slash(slash_commands, line)
            return

        turn_input = inject_inline_skills(line, skills) if skills is not None else line
        if _is_slash_line(line) and turn_input == line:
            await self._run_slash(slash_commands, line)
            return

        await self._run_turn(agent, turn_input)

    async def _run_slash(self, slash_commands: SlashCommands, line: str) -> None:
        try:
            message = await slash_commands.dispatch(line)
        except SlashCommandError as exc:
            await self.send_text(f"command error: {exc}")
            return
        await self.send_text(message)

    async def _run_turn(self, agent: Agent, user_input: str) -> None:
        async for event in agent.run_turn(user_input):
            await self.render_event(event)

    async def render_event(self, event: AgentEvent) -> None:
        """Render one agent event as channel text."""
        match event:
            case TextDelta():
                await self.send_text(event.text, end="")
            case ToolCallRequested():
                await self.send_text(
                    f"\ntool requested: {event.tool_call.name} {event.tool_call.arguments}"
                )
            case ToolCallStarted():
                await self.send_text(f"tool started: {event.tool_call.name}")
            case ToolCallCompleted():
                await self.send_text(f"tool result: {event.result.content}")
            case TurnComplete():
                await self.send_text("")

    async def send_text(self, text: str, *, end: str = "\n") -> None:
        """Send text to the channel."""
        raise NotImplementedError


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
