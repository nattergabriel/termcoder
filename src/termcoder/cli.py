"""Headless entry point — stdin/stdout REPL over the agent loop.

The TUI lands in step 7; this proves the wiring first. Text deltas stream
inline to stdout, tool requests and results render on their own lines, and
permission prompts read y/N from stdin. Ctrl-C cancels the current turn and
returns to the input prompt; Ctrl-D exits.
"""

import asyncio
import contextlib
import signal
import sys
from collections.abc import Iterator

from termcoder.agent.loop import Agent
from termcoder.composition import AppContext, build
from termcoder.config import load_config
from termcoder.events import (
    AgentEvent,
    TextDelta,
    ToolCallCompleted,
    ToolCallRequested,
    TurnComplete,
)
from termcoder.types import PermissionDecision, ToolCall


async def _read_line(prompt: str) -> str:
    print(prompt, end="", flush=True)
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()
    fd = sys.stdin.fileno()

    def complete_from_stdin() -> None:
        with contextlib.suppress(ValueError):
            loop.remove_reader(fd)
        line = sys.stdin.readline()
        if not line:
            future.set_exception(EOFError)
            return
        future.set_result(line.removesuffix("\n").removesuffix("\r"))

    loop.add_reader(fd, complete_from_stdin)
    try:
        return await future
    finally:
        with contextlib.suppress(ValueError):
            loop.remove_reader(fd)


async def _prompt_user(call: ToolCall) -> PermissionDecision:
    line = await _read_line(
        f"\n[permission] {call.name} {call.arguments} — allow? [y/N] ",
    )
    return "allow" if line.strip().lower() in {"y", "yes"} else "deny"


def _render(event: AgentEvent) -> None:
    match event:
        case TextDelta():
            print(event.text, end="", flush=True)
        case ToolCallRequested():
            print(f"\n[tool] {event.tool_call.name} {event.tool_call.arguments}")
        case ToolCallCompleted():
            marker = "tool-error" if event.result.is_error else "tool-ok"
            print(f"[{marker}] {event.result.content}")
        case TurnComplete():
            print()


async def _run_turn(agent: Agent, user_input: str) -> None:
    async for event in agent.run_turn(user_input):
        _render(event)


@contextlib.contextmanager
def _cancel_task_on_sigint(task: asyncio.Task[None]) -> Iterator[None]:
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
        loop.remove_signal_handler(signal.SIGINT)


async def _session(ctx: AppContext) -> None:
    while True:
        try:
            user_input = await _read_line("> ")
        except EOFError:
            print()
            return
        if not user_input.strip():
            continue

        current_turn = asyncio.create_task(_run_turn(ctx.agent, user_input))
        try:
            with _cancel_task_on_sigint(current_turn):
                await current_turn
        except asyncio.CancelledError:
            print("\n[turn cancelled]")


def main() -> None:
    config = load_config()
    ctx = build(config, _prompt_user)
    try:
        asyncio.run(_session(ctx))
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
