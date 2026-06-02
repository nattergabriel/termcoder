"""Smoke test: `Repl` driving `FakeProvider` through a scripted prompt session.

Uses prompt_toolkit's `create_pipe_input` + `DummyOutput` for input/output and
points rich's `Console` at an in-memory buffer, so the test exercises the full
REPL - input reading, streaming render, inline permission prompt, EOF exit -
without a real terminal.
"""

import io
from collections.abc import Sequence
from pathlib import Path

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from termcoder.agent.loop import Agent
from termcoder.commands.registry import SlashCommand, SlashCommands
from termcoder.events import TextDelta, ToolCallRequested
from termcoder.models import ToolCall
from termcoder.skills import Skill, SkillCatalog
from termcoder.tools.registry import Registry
from termcoder.ui.repl import Repl
from tests.fakes.fake_provider import FakeProvider

_NO_SLASH_COMMANDS = SlashCommands.from_iterable([])


async def test_repl_streams_text_and_exits_on_eof() -> None:
    """One user line is read, the response streams, Ctrl-D on the next prompt exits."""
    with create_pipe_input() as pt_input:
        # "\x04" is Ctrl-D — raises EOFError from the next prompt_async() call.
        pt_input.send_text("hello\n\x04")

        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=False, width=80)
        repl = Repl(console=console, input=pt_input, output=DummyOutput())

        provider = FakeProvider(scripts=[[TextDelta(text="world")]])
        agent = Agent(
            provider=provider,
            registry=Registry(),
            check_permission=repl.confirm_tool,
        )

        await repl.run(agent, _NO_SLASH_COMMANDS)

    assert "world" in buffer.getvalue()
    # The user's line was the only one sent to the provider.
    assert len(provider.received_calls) == 1
    assert provider.received_calls[0][0][-1].content == "hello"


async def test_repl_inline_permission_denial_round_trips_back_to_provider() -> None:
    """Tool call → inline `[y/N]` reads 'n' → denial passes back to the next provider call."""
    target_call = ToolCall(id="t1", name="write", arguments='{"path":"x","content":"y"}')

    with create_pipe_input() as pt_input:
        # user input, then permission decision, then Ctrl-D to exit.
        pt_input.send_text("do it\nn\n\x04")

        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=False, width=80)
        repl = Repl(console=console, input=pt_input, output=DummyOutput())

        provider = FakeProvider(
            scripts=[
                [ToolCallRequested(tool_call=target_call)],
                [TextDelta(text="ok, skipped")],
            ]
        )
        agent = Agent(
            provider=provider,
            registry=Registry(),
            check_permission=repl.confirm_tool,
        )

        await repl.run(agent, _NO_SLASH_COMMANDS)

    second_messages = provider.received_calls[1][0]
    tool_message = second_messages[-1]
    assert tool_message.role == "tool"
    assert "denied" in tool_message.content.lower()
    assert "ok, skipped" in buffer.getvalue()


async def test_repl_routes_slash_command_instead_of_calling_provider() -> None:
    """A `/` line invokes the registered slash handler and never reaches the provider."""
    received: list[Sequence[str]] = []

    async def handle(args: Sequence[str]) -> str:
        received.append(tuple(args))
        return "noted"

    slash_commands = SlashCommands.from_iterable([SlashCommand(name="note", handler=handle)])

    with create_pipe_input() as pt_input:
        pt_input.send_text("/note hello there\n\x04")

        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=False, width=80)
        repl = Repl(console=console, input=pt_input, output=DummyOutput())

        provider = FakeProvider(scripts=[])
        agent = Agent(
            provider=provider,
            registry=Registry(),
            check_permission=repl.confirm_tool,
        )

        await repl.run(agent, slash_commands)

    assert received == [("hello", "there")]
    assert "noted" in buffer.getvalue()
    assert provider.received_calls == []


async def test_repl_injects_inline_skill_tokens_into_normal_turn(tmp_path: Path) -> None:
    skill_dir = tmp_path / "python-testing"
    skill_dir.mkdir()
    location = skill_dir / "SKILL.md"
    location.write_text("", encoding="utf-8")
    skills = SkillCatalog(
        (
            Skill(
                name="python-testing",
                description="Write Python tests.",
                location=location,
                body="# Python Testing\nUse pytest.",
            ),
        )
    )

    with create_pipe_input() as pt_input:
        pt_input.send_text("please use /python-testing for this\n\x04")

        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=False, width=80)
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        provider = FakeProvider(scripts=[[TextDelta(text="ok")]])
        agent = Agent(provider=provider, registry=Registry(), check_permission=repl.confirm_tool)

        await repl.run(agent, _NO_SLASH_COMMANDS, skills)

    user_message = provider.received_calls[0][0][-1]
    assert user_message.content.startswith('<skill_content name="python-testing">')
    assert "# Python Testing" in user_message.content
    assert user_message.content.endswith("please use /python-testing for this")


async def test_repl_exact_skill_token_runs_turn_with_minimal_prompt(tmp_path: Path) -> None:
    skill_dir = tmp_path / "python-testing"
    skill_dir.mkdir()
    location = skill_dir / "SKILL.md"
    location.write_text("", encoding="utf-8")
    skills = SkillCatalog(
        (
            Skill(
                name="python-testing",
                description="Write Python tests.",
                location=location,
                body="# Python Testing\nUse pytest.",
            ),
        )
    )

    with create_pipe_input() as pt_input:
        pt_input.send_text("/python-testing\n\x04")

        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=False, width=80)
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        provider = FakeProvider(scripts=[[TextDelta(text="ok")]])
        agent = Agent(provider=provider, registry=Registry(), check_permission=repl.confirm_tool)

        await repl.run(agent, _NO_SLASH_COMMANDS, skills)

    user_message = provider.received_calls[0][0][-1]
    assert user_message.content.startswith('<skill_content name="python-testing">')
    assert user_message.content.endswith("Use the activated skill.")


async def test_repl_unknown_slash_line_still_reports_command_error() -> None:
    with create_pipe_input() as pt_input:
        pt_input.send_text("/unknown\n\x04")

        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=False, width=80)
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        provider = FakeProvider(scripts=[])
        agent = Agent(provider=provider, registry=Registry(), check_permission=repl.confirm_tool)

        await repl.run(agent, _NO_SLASH_COMMANDS)

    assert "unknown command: /unknown" in buffer.getvalue()
    assert provider.received_calls == []
