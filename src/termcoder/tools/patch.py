"""Patch tool."""

import re
from dataclasses import dataclass
from pathlib import Path

from termcoder.models import ToolCall, ToolName, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, optional_string, parse_object, required_string
from termcoder.tools.results import invalid_arguments, tool_failed

_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


@dataclass(frozen=True, slots=True)
class _Hunk:
    old_start: int
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _FilePatch:
    old_path: str
    new_path: str
    hunks: tuple[_Hunk, ...]


@dataclass(frozen=True, slots=True)
class _FileUpdate:
    path: Path
    content: str | None


class Patch:
    name: ToolName = "patch"
    schema: ToolSchema = ToolSchema(
        name="patch",
        description=(
            "Apply a simple unified diff to UTF-8 text files. Supports modifying, creating, "
            "and deleting files."
        ),
        parameters={
            "type": "object",
            "properties": {
                "patch": {
                    "type": "string",
                    "description": "Unified diff text to apply.",
                },
                "root": {
                    "type": "string",
                    "description": (
                        "Directory for relative diff paths. Defaults to the current directory."
                    ),
                },
            },
            "required": ["patch"],
        },
    )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = parse_object(call)
            patch_text = required_string(args, "patch")
            root = Path(optional_string(args, "root") or ".")
            file_patches = _parse_patch(patch_text)
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        try:
            updates = tuple(_plan_file_update(file_patch, root=root) for file_patch in file_patches)
            _commit_updates(updates)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            return tool_failed(call, "patch", exc)

        return ToolResult(
            tool_call_id=call.id,
            content=(
                f"applied patch to {len(updates)} file(s): "
                f"{', '.join(str(update.path) for update in updates)}"
            ),
        )


def _parse_patch(patch_text: str) -> tuple[_FilePatch, ...]:
    if patch_text == "":
        raise ArgumentError("'patch' must not be empty")

    lines = patch_text.splitlines(keepends=True)
    index = 0
    patches: list[_FilePatch] = []
    while index < len(lines):
        line = lines[index]
        if not line.startswith("--- "):
            index += 1
            continue
        old_path = _parse_path_header(line, "---")
        index += 1
        if index >= len(lines) or not lines[index].startswith("+++ "):
            raise ArgumentError("expected +++ path header after --- path header")
        new_path = _parse_path_header(lines[index], "+++")
        index += 1

        hunks: list[_Hunk] = []
        while index < len(lines) and lines[index].startswith("@@ "):
            hunk, index = _parse_hunk(lines, index)
            hunks.append(hunk)
        if not hunks:
            raise ArgumentError(f"expected at least one hunk for {new_path}")
        patches.append(_FilePatch(old_path=old_path, new_path=new_path, hunks=tuple(hunks)))

    if not patches:
        raise ArgumentError("expected unified diff with ---/+++ headers")
    return tuple(patches)


def _parse_path_header(line: str, marker: str) -> str:
    value = line.removeprefix(f"{marker} ").strip()
    if "\t" in value:
        value = value.split("\t", maxsplit=1)[0]
    if value == "":
        raise ArgumentError(f"{marker} path header must not be empty")
    return value


def _parse_hunk(lines: list[str], index: int) -> tuple[_Hunk, int]:
    header = lines[index]
    match = _HUNK_HEADER_RE.match(header)
    if match is None:
        raise ArgumentError(f"invalid hunk header: {header.rstrip()}")

    old_start = int(match.group("old_start"))
    old_count = _parse_count(match.group("old_count"))
    new_count = _parse_count(match.group("new_count"))
    index += 1

    hunk_lines: list[str] = []
    removed_or_context = 0
    added_or_context = 0
    while index < len(lines) and (
        removed_or_context < old_count
        or added_or_context < new_count
        or lines[index].startswith("\\ No newline at end of file")
    ):
        line = lines[index]
        if line.startswith("\\ No newline at end of file"):
            if not hunk_lines:
                raise ArgumentError("no-newline marker must follow a hunk line")
            hunk_lines[-1] = _strip_line_ending(hunk_lines[-1])
            index += 1
            continue
        if not line.startswith((" ", "-", "+")):
            raise ArgumentError(f"invalid hunk line: {line.rstrip()}")
        hunk_lines.append(line)
        if line.startswith((" ", "-")):
            removed_or_context += 1
        if line.startswith((" ", "+")):
            added_or_context += 1
        if removed_or_context > old_count:
            raise ArgumentError("hunk removed/context line count exceeds header")
        if added_or_context > new_count:
            raise ArgumentError("hunk added/context line count exceeds header")
        index += 1

    if removed_or_context != old_count:
        raise ArgumentError("hunk removed/context line count does not match header")
    if added_or_context != new_count:
        raise ArgumentError("hunk added/context line count does not match header")
    return (
        _Hunk(
            old_start=old_start,
            lines=tuple(hunk_lines),
        ),
        index,
    )


def _parse_count(value: str | None) -> int:
    return 1 if value is None else int(value)


def _strip_line_ending(line: str) -> str:
    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    return line


def _plan_file_update(file_patch: _FilePatch, *, root: Path) -> _FileUpdate:
    target_path = _target_path(file_patch, root=root)
    if file_patch.old_path == "/dev/null":
        original_lines: list[str] = []
    else:
        original_lines = target_path.read_text(encoding="utf-8").splitlines(keepends=True)

    updated_lines = _apply_hunks(original_lines, file_patch.hunks, display_path=str(target_path))

    if file_patch.new_path == "/dev/null":
        if updated_lines:
            raise ValueError(f"delete patch did not remove all content from {target_path}")
        return _FileUpdate(path=target_path, content=None)

    return _FileUpdate(path=target_path, content="".join(updated_lines))


def _commit_updates(updates: tuple[_FileUpdate, ...]) -> None:
    rollbacks: list[tuple[Path, bytes | None]] = []
    try:
        for update in updates:
            original_content = update.path.read_bytes() if update.path.exists() else None
            rollbacks.append((update.path, original_content))
            if update.content is None:
                update.path.unlink()
            else:
                update.path.write_text(update.content, encoding="utf-8")
    except OSError:
        _rollback(rollbacks)
        raise


def _rollback(rollbacks: list[tuple[Path, bytes | None]]) -> None:
    for path, content in reversed(rollbacks):
        try:
            if content is not None:
                path.write_bytes(content)
            elif path.exists():
                path.unlink()
        except OSError:
            continue


def _target_path(file_patch: _FilePatch, *, root: Path) -> Path:
    path = file_patch.old_path if file_patch.new_path == "/dev/null" else file_patch.new_path
    normalized = _normalize_diff_path(path)
    target = Path(normalized)
    if target.is_absolute():
        return target
    return root / target


def _normalize_diff_path(path: str) -> str:
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def _apply_hunks(
    original_lines: list[str], hunks: tuple[_Hunk, ...], *, display_path: str
) -> list[str]:
    updated_lines: list[str] = []
    cursor = 0
    for hunk in hunks:
        hunk_index = max(hunk.old_start - 1, 0)
        if hunk_index < cursor:
            raise ValueError(f"overlapping hunks for {display_path}")
        updated_lines.extend(original_lines[cursor:hunk_index])
        cursor = _apply_hunk(
            original_lines,
            updated_lines,
            cursor=hunk_index,
            hunk=hunk,
            display_path=display_path,
        )
    updated_lines.extend(original_lines[cursor:])
    return updated_lines


def _apply_hunk(
    original_lines: list[str],
    updated_lines: list[str],
    *,
    cursor: int,
    hunk: _Hunk,
    display_path: str,
) -> int:
    for line in hunk.lines:
        prefix = line[0]
        content = line[1:]
        if prefix == "+":
            updated_lines.append(content)
            continue
        if cursor >= len(original_lines) or original_lines[cursor] != content:
            raise ValueError(f"hunk context did not match {display_path} at line {cursor + 1}")
        if prefix == " ":
            updated_lines.append(original_lines[cursor])
        cursor += 1
    return cursor
