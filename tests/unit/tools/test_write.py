"""Tests for the Write tool — real filesystem I/O via `tmp_path`."""

import json
from pathlib import Path

from termcoder.models import ToolCall
from termcoder.tools.write import Write


async def test_creates_new_file(tmp_path: Path) -> None:
    target = tmp_path / "new.txt"

    result = await Write().run(_call({"path": str(target), "content": "hi"}))

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == "hi"


async def test_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("old", encoding="utf-8")

    result = await Write().run(_call({"path": str(target), "content": "new"}))

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == "new"


async def test_reports_missing_parent_dir_as_tool_error(tmp_path: Path) -> None:
    target = tmp_path / "missing-dir" / "file.txt"

    result = await Write().run(_call({"path": str(target), "content": "x"}))

    assert result.is_error is True
    assert "write failed" in result.content


async def test_rejects_malformed_json_arguments() -> None:
    result = await Write().run(ToolCall(id="c1", name="write", arguments="not json"))

    assert result.is_error is True
    assert "invalid arguments" in result.content


async def test_rejects_missing_content_key(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"

    result = await Write().run(_call({"path": str(target)}))

    assert result.is_error is True
    assert "invalid arguments" in result.content


def _call(args: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name="write", arguments=json.dumps(args))
