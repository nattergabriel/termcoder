"""Unit tests for `Repl` helpers — focused on cancellation wiring."""

import asyncio
import io

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from termcoder.events import TextDelta, ToolCallCompleted, ToolCallRequested, TurnComplete
from termcoder.models import ToolCall, ToolResult
from termcoder.ui.repl import Repl


async def test_sigint_handler_only_cancels_active_turn() -> None:
    loop = asyncio.get_running_loop()
    original_add_signal_handler = loop.add_signal_handler
    original_remove_signal_handler = loop.remove_signal_handler
    captured_handler: list[object] = []
    removed_signals: list[int] = []

    def fake_add_signal_handler(signum: int, callback: object, *args: object) -> None:
        captured_handler.append(callback)

    def fake_remove_signal_handler(signum: int) -> bool:
        removed_signals.append(signum)
        return True

    loop.add_signal_handler = fake_add_signal_handler  # type: ignore[assignment,method-assign]
    loop.remove_signal_handler = fake_remove_signal_handler  # type: ignore[assignment,method-assign]
    try:
        with create_pipe_input() as pt_input:
            repl = Repl(input=pt_input, output=DummyOutput())
            turn = asyncio.create_task(asyncio.sleep(60))
            with repl._cancel_on_sigint(turn):
                assert len(captured_handler) == 1
                callback = captured_handler[0]
                assert callable(callback)
                callback()
                with pytest.raises(asyncio.CancelledError):
                    await turn
            assert removed_signals
    finally:
        loop.add_signal_handler = original_add_signal_handler  # type: ignore[method-assign]
        loop.remove_signal_handler = original_remove_signal_handler  # type: ignore[method-assign]


async def test_render_escapes_rich_markup_in_tool_output() -> None:
    """Bracketed tool output (e.g. bash's `[exit 1]`) must not be parsed as Rich markup."""
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=80)
    with create_pipe_input() as pt_input:
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        repl._render(
            ToolCallCompleted(
                result=ToolResult(tool_call_id="t1", content="[exit 1] boom", is_error=True),
            )
        )

    assert "[exit 1] boom" in buffer.getvalue()


async def test_banner_renders_once() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    with create_pipe_input() as pt_input:
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        repl._render_banner()
        repl._render_banner()

    output = buffer.getvalue()
    assert output.count("termcoder") == 1
    assert "Ctrl-D exits" in output
    assert "┌" not in output
    assert "─" not in output


async def test_assistant_renders_without_message_panel() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    with create_pipe_input() as pt_input:
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        repl._render(TextDelta(text="world"))
        repl._close_live()

    output = buffer.getvalue()
    assert "world" in output
    assert "assistant" not in output


async def test_multiline_assistant_output_keeps_continuation_indent() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    with create_pipe_input() as pt_input:
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        repl._render(TextDelta(text="first\nsecond"))
        repl._close_live()

    output = buffer.getvalue()
    assert "* first" in output
    assert "  second" in output


async def test_turn_complete_adds_spacing_before_next_prompt() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    with create_pipe_input() as pt_input:
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        repl._render(TextDelta(text="done"))
        repl._render(TurnComplete())

    output = buffer.getvalue()
    assert output.endswith("\n")
    assert not output.endswith("\n\n")


async def test_waiting_spinner_is_replaced_by_assistant_stream() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    with create_pipe_input() as pt_input:
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        repl._start_waiting()
        assert repl._live_mode == "waiting"
        repl._render(TextDelta(text="done"))
        live_mode: object = repl._live_mode
        assert live_mode == "assistant"
        repl._close_live()

    assert "done" in buffer.getvalue()


async def test_tool_request_renders_compact_command_preview() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    with create_pipe_input() as pt_input:
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        repl._render(
            ToolCallRequested(
                tool_call=ToolCall(
                    id="t1",
                    name="bash",
                    arguments='{"command": "ls -la"}',
                )
            )
        )

    output = buffer.getvalue()
    assert "● Bash(ls -la)" in output
    assert '{"command"' not in output
    assert "tool request" not in output


async def test_tool_output_is_truncated_to_five_lines() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    content = "\n".join([f"line {line}" for line in range(1, 8)])
    with create_pipe_input() as pt_input:
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        repl._render(
            ToolCallCompleted(
                result=ToolResult(tool_call_id="t1", content=content),
            )
        )

    output = buffer.getvalue()
    assert "  └ Tool completed" in output
    assert "line 1" in output
    assert "line 5" in output
    assert "line 6" not in output
    assert "... 2 more lines" in output


async def test_tool_result_adds_spacing_before_followup_assistant_text() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    with create_pipe_input() as pt_input:
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        repl._render(
            ToolCallCompleted(
                result=ToolResult(tool_call_id="t1", content="result"),
            )
        )
        repl._render(TextDelta(text="next"))
        repl._close_live()

    output = buffer.getvalue()
    assert "result\n\n* next" in output


async def test_read_tool_result_summarizes_line_count_in_group() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    with create_pipe_input() as pt_input:
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        repl._render(
            ToolCallRequested(
                tool_call=ToolCall(
                    id="t1",
                    name="read",
                    arguments='{"path": "src/termcoder/ui/repl.py"}',
                )
            )
        )
        repl._render(
            ToolCallCompleted(
                result=ToolResult(tool_call_id="t1", content="first\nsecond\nthird"),
            )
        )

    output = buffer.getvalue()
    assert "● Read(src/termcoder/ui/repl.py)" in output
    assert "  └ Read(src/termcoder/ui/repl.py): Read 3 lines" in output


async def test_multiple_tool_results_identify_their_matching_request() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    with create_pipe_input() as pt_input:
        repl = Repl(console=console, input=pt_input, output=DummyOutput())
        repl._render(
            ToolCallRequested(
                tool_call=ToolCall(
                    id="read-call",
                    name="read",
                    arguments='{"path": "a.py"}',
                )
            )
        )
        repl._render(
            ToolCallRequested(
                tool_call=ToolCall(
                    id="bash-call",
                    name="bash",
                    arguments='{"command": "ls"}',
                )
            )
        )
        repl._render(
            ToolCallCompleted(
                result=ToolResult(tool_call_id="read-call", content="first\nsecond"),
            )
        )
        repl._render(
            ToolCallCompleted(
                result=ToolResult(tool_call_id="bash-call", content="out"),
            )
        )

    output = buffer.getvalue()
    assert "● Read(a.py)" in output
    assert "● Bash(ls)" in output
    assert "  └ Read(a.py): Read 2 lines" in output
    assert "  └ Bash(ls): Tool completed" in output
