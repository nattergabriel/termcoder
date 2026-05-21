"""Tests for the Patch tool — real filesystem I/O via `tmp_path`."""

import json
from pathlib import Path

from termcoder.models import ToolCall
from termcoder.tools.patch import Patch


async def test_applies_unified_diff_to_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    patch = """--- a/note.txt
+++ b/note.txt
@@ -1,3 +1,3 @@
 alpha
-beta
+delta
 gamma
"""

    result = await Patch().run(_call({"root": str(tmp_path), "patch": patch}))

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == "alpha\ndelta\ngamma\n"
    assert "applied patch to 1 file" in result.content


async def test_creates_file_from_dev_null(tmp_path: Path) -> None:
    target = tmp_path / "new.txt"
    patch = """--- /dev/null
+++ b/new.txt
@@ -0,0 +1,2 @@
+hello
+world
"""

    result = await Patch().run(_call({"root": str(tmp_path), "patch": patch}))

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == "hello\nworld\n"


async def test_deletes_file_to_dev_null(tmp_path: Path) -> None:
    target = tmp_path / "gone.txt"
    target.write_text("bye\n", encoding="utf-8")
    patch = """--- a/gone.txt
+++ /dev/null
@@ -1 +0,0 @@
-bye
"""

    result = await Patch().run(_call({"root": str(tmp_path), "patch": patch}))

    assert result.is_error is False
    assert not target.exists()


async def test_reports_context_mismatch_without_changing_file(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    patch = """--- a/note.txt
+++ b/note.txt
@@ -1,2 +1,2 @@
 alpha
-missing
+delta
"""

    result = await Patch().run(_call({"root": str(tmp_path), "patch": patch}))

    assert result.is_error is True
    assert "context did not match" in result.content
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\n"


async def test_failed_multi_file_patch_leaves_all_files_unchanged(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("alpha\n", encoding="utf-8")
    second.write_text("beta\n", encoding="utf-8")
    patch = """--- a/first.txt
+++ b/first.txt
@@ -1 +1 @@
-alpha
+changed
--- a/second.txt
+++ b/second.txt
@@ -1 +1 @@
-missing
+changed
"""

    result = await Patch().run(_call({"root": str(tmp_path), "patch": patch}))

    assert result.is_error is True
    assert "context did not match" in result.content
    assert first.read_text(encoding="utf-8") == "alpha\n"
    assert second.read_text(encoding="utf-8") == "beta\n"


async def test_applies_patch_for_file_without_final_newline(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("old", encoding="utf-8")
    patch = """--- a/note.txt
+++ b/note.txt
@@ -1 +1 @@
-old
\\ No newline at end of file
+new
\\ No newline at end of file
"""

    result = await Patch().run(_call({"root": str(tmp_path), "patch": patch}))

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == "new"


async def test_can_patch_file_lines_that_start_with_diff_markers(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("-- marker\n++ marker\n", encoding="utf-8")
    patch = """--- a/note.txt
+++ b/note.txt
@@ -1,2 +1,2 @@
--- marker
-++ marker
+-- changed
+++ changed
"""

    result = await Patch().run(_call({"root": str(tmp_path), "patch": patch}))

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == "-- changed\n++ changed\n"


async def test_rejects_malformed_patch() -> None:
    result = await Patch().run(_call({"patch": "not a diff"}))

    assert result.is_error is True
    assert "expected unified diff" in result.content


async def test_rejects_malformed_json_arguments() -> None:
    result = await Patch().run(ToolCall(id="c1", name="patch", arguments="not json"))

    assert result.is_error is True
    assert "invalid arguments" in result.content


def _call(args: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name="patch", arguments=json.dumps(args))
