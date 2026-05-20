"""Tests for the Read tool — real filesystem I/O via `tmp_path`."""

import json
from pathlib import Path

from termcoder.models import ToolCall
from termcoder.tools.read import Read


async def test_returns_file_contents(tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    target.write_text("hello world\n", encoding="utf-8")

    result = await Read().run(_call({"path": str(target)}))

    assert result.tool_call_id == "c1"
    assert result.content == "hello world\n"
    assert result.is_error is False


async def test_reports_missing_file_as_tool_error(tmp_path: Path) -> None:
    missing = tmp_path / "nope.txt"

    result = await Read().run(_call({"path": str(missing)}))

    assert result.is_error is True
    assert "nope.txt" in result.content


async def test_reports_directory_as_tool_error(tmp_path: Path) -> None:
    result = await Read().run(_call({"path": str(tmp_path)}))

    assert result.is_error is True


async def test_reports_non_utf8_as_tool_error(tmp_path: Path) -> None:
    binary = tmp_path / "binary.bin"
    binary.write_bytes(b"\xff\xfe\x00\x01")

    result = await Read().run(_call({"path": str(binary)}))

    assert result.is_error is True
    assert "utf-8" in result.content.lower() or "codec" in result.content.lower()


async def test_returns_requested_line_window(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

    result = await Read().run(_call({"path": str(target), "start_line": 2, "limit": 2}))

    assert result.is_error is False
    assert result.content == "two\nthree\n"


async def test_line_window_can_start_past_end(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("one\n", encoding="utf-8")

    result = await Read().run(_call({"path": str(target), "start_line": 10}))

    assert result.is_error is False
    assert result.content == ""


async def test_rejects_invalid_line_window(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("one\n", encoding="utf-8")

    result = await Read().run(_call({"path": str(target), "start_line": 0}))

    assert result.is_error is True
    assert "start_line" in result.content


async def test_rejects_malformed_json_arguments() -> None:
    result = await Read().run(_raw_call("not json"))

    assert result.is_error is True
    assert "invalid arguments" in result.content


async def test_rejects_missing_path_key() -> None:
    result = await Read().run(_call({}))

    assert result.is_error is True
    assert "invalid arguments" in result.content


def _call(args: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name="read", arguments=json.dumps(args))


def _raw_call(arguments: str) -> ToolCall:
    return ToolCall(id="c1", name="read", arguments=arguments)
