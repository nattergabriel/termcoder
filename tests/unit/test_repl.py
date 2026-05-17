"""Unit tests for `Repl` helpers — focused on cancellation wiring."""

import asyncio

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from termcoder.repl import Repl


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
