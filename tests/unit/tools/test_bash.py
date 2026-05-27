"""Tests for the Bash tool — real subprocesses, no shelling out to /bin/sh in tests would
defeat the point of the tool.
"""

import asyncio
import json
from pathlib import Path

from termcoder.models import ToolCall
from termcoder.tools.bash import Bash


async def test_captures_stdout_and_exit_zero() -> None:
    result = await Bash().run(_call("echo hello"))

    assert result.is_error is False
    assert "hello" in result.content
    assert "[exit 0]" in result.content


async def test_marks_nonzero_exit_as_error_and_includes_exit_code() -> None:
    result = await Bash().run(_call("false"))

    assert result.is_error is True
    assert "[exit 1]" in result.content


async def test_captures_stderr() -> None:
    result = await Bash().run(_call("echo oops 1>&2; exit 2"))

    assert result.is_error is True
    assert "oops" in result.content
    assert "[exit 2]" in result.content


async def test_returns_only_exit_line_when_no_output() -> None:
    result = await Bash().run(_call("true"))

    assert result.is_error is False
    assert result.content == "[exit 0]"


async def test_rejects_malformed_json_arguments() -> None:
    result = await Bash().run(ToolCall(id="c1", name="bash", arguments="not json"))

    assert result.is_error is True
    assert "invalid arguments" in result.content


async def test_rejects_missing_command_key() -> None:
    result = await Bash().run(_call_args({}))

    assert result.is_error is True
    assert "invalid arguments" in result.content


async def test_stdin_is_closed_so_reading_commands_do_not_hang() -> None:
    result = await asyncio.wait_for(Bash().run(_call("cat")), timeout=2.0)

    assert result.is_error is False
    assert result.content == "[exit 0]"


async def test_rejects_non_string_command() -> None:
    result = await Bash().run(_call_args({"command": 123}))

    assert result.is_error is True
    assert "command" in result.content


async def test_runs_command_in_requested_cwd(tmp_path: Path) -> None:
    result = await Bash().run(_call_args({"command": "pwd", "cwd": str(tmp_path)}))

    assert result.is_error is False
    assert str(tmp_path) in result.content


async def test_times_out_long_running_command() -> None:
    result = await Bash().run(_call_args({"command": "sleep 2", "timeout_seconds": 1}))

    assert result.is_error is True
    assert "timed out" in result.content


async def test_truncates_large_output() -> None:
    result = await Bash().run(_call_args({"command": "printf abcdef", "max_chars": 3}))

    assert result.is_error is False
    assert "[truncated to 3 characters]" in result.content
    assert "[exit 0]" in result.content


def _call(command: str) -> ToolCall:
    return _call_args({"command": command})


def _call_args(args: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name="bash", arguments=json.dumps(args))
