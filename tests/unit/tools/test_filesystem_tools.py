"""Tests for filesystem mutation tools."""

import json
from pathlib import Path

from termcoder.models import ToolCall
from termcoder.tools.delete import Delete
from termcoder.tools.move import Move


async def test_move_renames_file(tmp_path: Path) -> None:
    source = tmp_path / "old.txt"
    destination = tmp_path / "new.txt"
    source.write_text("hello\n", encoding="utf-8")

    result = await Move().run(
        _call("move", {"source": str(source), "destination": str(destination)})
    )

    assert result.is_error is False
    assert not source.exists()
    assert destination.read_text(encoding="utf-8") == "hello\n"


async def test_move_refuses_to_overwrite_by_default(tmp_path: Path) -> None:
    source = tmp_path / "old.txt"
    destination = tmp_path / "new.txt"
    source.write_text("old\n", encoding="utf-8")
    destination.write_text("new\n", encoding="utf-8")

    result = await Move().run(
        _call("move", {"source": str(source), "destination": str(destination)})
    )

    assert result.is_error is True
    assert source.exists()
    assert destination.read_text(encoding="utf-8") == "new\n"


async def test_delete_removes_file(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("hello\n", encoding="utf-8")

    result = await Delete().run(_call("delete", {"path": str(target)}))

    assert result.is_error is False
    assert not target.exists()


async def test_delete_requires_recursive_for_directory(tmp_path: Path) -> None:
    target = tmp_path / "dir"
    target.mkdir()

    result = await Delete().run(_call("delete", {"path": str(target)}))

    assert result.is_error is True
    assert target.exists()


async def test_delete_removes_directory_recursively(tmp_path: Path) -> None:
    target = tmp_path / "dir"
    target.mkdir()
    (target / "note.txt").write_text("hello\n", encoding="utf-8")

    result = await Delete().run(_call("delete", {"path": str(target), "recursive": True}))

    assert result.is_error is False
    assert not target.exists()


def _call(name: str, args: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=json.dumps(args))
