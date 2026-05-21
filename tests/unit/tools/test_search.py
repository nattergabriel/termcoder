"""Tests for the Search tool — real filesystem I/O via `tmp_path`."""

import json
from pathlib import Path

from termcoder.models import ToolCall
from termcoder.tools.search import Search


async def test_searches_plain_text_in_directory(tmp_path: Path) -> None:
    (tmp_path / "one.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    (tmp_path / "two.txt").write_text("gamma\nalphabet\n", encoding="utf-8")

    result = await Search().run(_call({"path": str(tmp_path), "query": "alpha"}))

    assert result.is_error is False
    assert "one.txt:1: alpha" in result.content
    assert "two.txt:2: alphabet" in result.content
    assert "found 2 match" in result.content


async def test_searches_single_file_with_regex(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("issue-123\nissue-abc\n", encoding="utf-8")

    result = await Search().run(_call({"path": str(target), "query": r"issue-\d+", "regex": True}))

    assert result.is_error is False
    assert f"{target}:1: issue-123" in result.content
    assert "issue-abc" not in result.content


async def test_can_search_case_insensitively(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("Alpha\n", encoding="utf-8")

    result = await Search().run(
        _call({"path": str(target), "query": "alpha", "case_sensitive": False})
    )

    assert result.is_error is False
    assert "Alpha" in result.content


async def test_limits_results(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("hit\nhit\nhit\n", encoding="utf-8")

    result = await Search().run(_call({"path": str(target), "query": "hit", "limit": 2}))

    assert result.is_error is False
    assert result.content.count("hit") == 2
    assert "showing first 2 match" in result.content


async def test_rejects_zero_limit(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("hit\n", encoding="utf-8")

    result = await Search().run(_call({"path": str(target), "query": "hit", "limit": 0}))

    assert result.is_error is True
    assert "limit" in result.content


async def test_skips_non_utf8_files(tmp_path: Path) -> None:
    (tmp_path / "good.txt").write_text("needle\n", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\xff\xfe")

    result = await Search().run(_call({"path": str(tmp_path), "query": "needle"}))

    assert result.is_error is False
    assert "good.txt:1: needle" in result.content
    assert "skipped 1" in result.content


async def test_reports_missing_path_as_tool_error(tmp_path: Path) -> None:
    result = await Search().run(_call({"path": str(tmp_path / "missing"), "query": "x"}))

    assert result.is_error is True
    assert "does not exist" in result.content


async def test_rejects_invalid_regex(tmp_path: Path) -> None:
    result = await Search().run(_call({"path": str(tmp_path), "query": "[", "regex": True}))

    assert result.is_error is True
    assert "invalid regex" in result.content


async def test_rejects_empty_query(tmp_path: Path) -> None:
    result = await Search().run(_call({"path": str(tmp_path), "query": ""}))

    assert result.is_error is True
    assert "must not be empty" in result.content


def _call(args: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name="search", arguments=json.dumps(args))
