"""Terminal channel."""

from prompt_toolkit import PromptSession
from prompt_toolkit.input import Input
from prompt_toolkit.output import Output
from rich.console import Console

from termcoder.agent.loop import Agent
from termcoder.channels.base import BaseChannel
from termcoder.commands.registry import SlashCommands
from termcoder.models import PermissionDecision, ToolCall
from termcoder.skills import SkillCatalog


class TerminalChannel(BaseChannel):
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
        await self.send_text(f"tool permission requested: {call.name} {call.arguments}")
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
        await self._render_banner(slash_commands)
        while True:
            try:
                user_input = await self._session.prompt_async("you > ")
            except EOFError:
                return
            except KeyboardInterrupt:
                await self.send_text("cancelled")
                continue

            await self.handle_user_input(agent, slash_commands, user_input, skills)

    async def send_text(self, text: str, *, end: str = "\n") -> None:
        """Print text to the terminal."""
        self._console.print(text, end=end)

    async def _render_banner(self, slash_commands: SlashCommands) -> None:
        commands = ", ".join(f"/{name}" for name in slash_commands.names())
        if commands:
            await self.send_text(f"termcoder ({commands})")
            return
        await self.send_text("termcoder")
