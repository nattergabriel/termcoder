"""Tests for the ListFiles tool."""

import json
from pathlib import Path

from termcoder.models import ToolCall
from termcoder.tools.list_files import ListFiles


async def test_lists_files_and_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")

    result = await ListFiles().run(_call({"path": str(tmp_path)}))

    assert result.is_error is False
    assert "src/" in result.content
    assert "src/app.py" in result.content
    assert "README.md" in result.content


async def test_respects_max_depth(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "mod.py").write_text("", encoding="utf-8")

    result = await ListFiles().run(_call({"path": str(tmp_path), "max_depth": 0}))

    assert result.is_error is False
    assert "src/" in result.content
    assert "src/pkg/" not in result.content


async def test_ignores_common_generated_directories(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "app.py").write_text("", encoding="utf-8")

    result = await ListFiles().run(_call({"path": str(tmp_path)}))

    assert result.is_error is False
    assert "app.py" in result.content
    assert ".git" not in result.content
    assert "node_modules" not in result.content


async def test_reports_missing_path_as_tool_error(tmp_path: Path) -> None:
    result = await ListFiles().run(_call({"path": str(tmp_path / "missing")}))

    assert result.is_error is True
    assert "list_files failed" in result.content


async def test_rejects_invalid_limit() -> None:
    result = await ListFiles().run(_call({"limit": 0}))

    assert result.is_error is True
    assert "limit" in result.content


async def test_rejects_empty_path() -> None:
    result = await ListFiles().run(_call({"path": ""}))

    assert result.is_error is True
    assert "path" in result.content


def _call(args: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name="list_files", arguments=json.dumps(args))
