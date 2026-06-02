"""Channel protocol."""

from typing import Protocol

from termcoder.agent.loop import Agent
from termcoder.commands.registry import SlashCommands
from termcoder.models import PermissionDecision, ToolCall
from termcoder.skills import SkillCatalog


class Channel(Protocol):
    """A user-facing interaction channel."""

    async def confirm_tool(self, call: ToolCall) -> PermissionDecision:
        """Prompt the user for a tool-call permission decision."""
        ...

    async def run(
        self,
        agent: Agent,
        slash_commands: SlashCommands,
        skills: SkillCatalog | None = None,
    ) -> None:
        """Run the channel until it exits."""
        ...
