"""Unit tests for CLI input and cancellation helpers."""

import asyncio
import os
import sys
from collections.abc import Iterator

import pytest

from termcoder.cli import _cancel_task_on_sigint, _read_line


@pytest.fixture
def pipe_stdin(monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    read_fd, write_fd = os.pipe()
    stdin = os.fdopen(read_fd, encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin)
    try:
        yield write_fd
    finally:
        stdin.close()
        os.close(write_fd)


async def test_read_line_reads_from_stdin_without_worker_thread(
    pipe_stdin: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def write_line() -> None:
        await asyncio.sleep(0)
        os.write(pipe_stdin, b"hello\n")

    writer = asyncio.create_task(write_line())

    line = await _read_line("> ")

    await writer
    assert line == "hello"
    assert capsys.readouterr().out == "> "


async def test_read_line_removes_reader_when_cancelled(pipe_stdin: int) -> None:
    task = asyncio.create_task(_read_line("> "))
    await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # A later line should not be consumed by the cancelled read.
    os.write(pipe_stdin, b"late\n")
    assert await _read_line("> ") == "late"


async def test_read_line_falls_back_when_add_reader_is_not_supported(
    pipe_stdin: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    loop = asyncio.get_running_loop()
    original_add_reader = loop.add_reader

    def unsupported_add_reader(fd: int, callback: object, *args: object) -> None:
        raise NotImplementedError

    loop.add_reader = unsupported_add_reader  # type: ignore[assignment,method-assign]
    try:

        async def write_line() -> None:
            await asyncio.sleep(0)
            os.write(pipe_stdin, b"windows\n")

        writer = asyncio.create_task(write_line())

        line = await _read_line("> ")

        await writer
    finally:
        loop.add_reader = original_add_reader  # type: ignore[method-assign]

    assert line == "windows"
    assert capsys.readouterr().out == "> "


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
        turn = asyncio.create_task(asyncio.sleep(60))
        with _cancel_task_on_sigint(turn):
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
