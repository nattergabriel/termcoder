"""Tests for the Edit tool — real filesystem I/O via `tmp_path`."""

import json
from pathlib import Path

from termcoder.models import ToolCall
from termcoder.tools.edit import Edit


async def test_replaces_single_exact_match(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    result = await Edit().run(_call({"path": str(target), "old": "beta", "new": "delta"}))

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == "alpha\ndelta\ngamma\n"
    assert "replaced 1 occurrence" in result.content


async def test_reports_missing_file_as_tool_error(tmp_path: Path) -> None:
    target = tmp_path / "missing.txt"

    result = await Edit().run(_call({"path": str(target), "old": "x", "new": "y"}))

    assert result.is_error is True
    assert "edit failed" in result.content


async def test_reports_missing_old_text_without_changing_file(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("alpha\n", encoding="utf-8")

    result = await Edit().run(_call({"path": str(target), "old": "beta", "new": "delta"}))

    assert result.is_error is True
    assert "not found" in result.content
    assert target.read_text(encoding="utf-8") == "alpha\n"


async def test_rejects_multiple_matches_by_default(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("same\nsame\n", encoding="utf-8")

    result = await Edit().run(_call({"path": str(target), "old": "same", "new": "changed"}))

    assert result.is_error is True
    assert "matched 2 times" in result.content
    assert target.read_text(encoding="utf-8") == "same\nsame\n"


async def test_can_replace_all_matches(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("same\nsame\n", encoding="utf-8")

    result = await Edit().run(
        _call({"path": str(target), "old": "same", "new": "changed", "replace_all": True})
    )

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == "changed\nchanged\n"
    assert "replaced 2 occurrence" in result.content


async def test_rejects_empty_old_text(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("alpha\n", encoding="utf-8")

    result = await Edit().run(_call({"path": str(target), "old": "", "new": "x"}))

    assert result.is_error is True
    assert "must not be empty" in result.content
    assert target.read_text(encoding="utf-8") == "alpha\n"


async def test_rejects_malformed_json_arguments() -> None:
    result = await Edit().run(ToolCall(id="c1", name="edit", arguments="not json"))

    assert result.is_error is True
    assert "invalid arguments" in result.content


async def test_rejects_non_string_new_value(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("alpha\n", encoding="utf-8")

    result = await Edit().run(_call({"path": str(target), "old": "alpha", "new": 123}))

    assert result.is_error is True
    assert "new" in result.content


def _call(args: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name="edit", arguments=json.dumps(args))
