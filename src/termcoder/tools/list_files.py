"""List files tool."""

from pathlib import Path

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import (
    ArgumentError,
    optional_int,
    optional_string,
    parse_object,
)
from termcoder.tools.results import invalid_arguments, tool_failed

_IGNORED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
}
_DEFAULT_MAX_DEPTH = 2
_DEFAULT_LIMIT = 200


class ListFiles:
    schema: ToolSchema = ToolSchema(
        name="list_files",
        description=(
            "List files and directories under a path. Returns relative paths, with directories "
            "ending in '/'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory to list. Defaults to the current directory.",
                },
                "max_depth": {
                    "type": "integer",
                    "description": (
                        "Maximum directory depth to descend into. "
                        f"Defaults to {_DEFAULT_MAX_DEPTH}."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": f"Maximum entries to return. Defaults to {_DEFAULT_LIMIT}.",
                },
            },
        },
    )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = parse_object(call)
            path = Path(optional_string(args, "path") or ".")
            max_depth = optional_int(args, "max_depth")
            limit = optional_int(args, "limit")
            max_depth = _DEFAULT_MAX_DEPTH if max_depth is None else max_depth
            limit = _DEFAULT_LIMIT if limit is None else limit
            if max_depth < 0:
                raise ArgumentError("'max_depth' must be at least 0")
            if limit < 1:
                raise ArgumentError("'limit' must be at least 1")
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        try:
            entries = _list_entries(path, max_depth=max_depth, limit=limit)
        except OSError as exc:
            return tool_failed(call, "list_files", exc)

        if not entries:
            return ToolResult(tool_call_id=call.id, content=f"no entries under {path}")
        summary = f"listed {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"
        if len(entries) >= limit:
            summary += f"; showing first {limit}"
        return ToolResult(tool_call_id=call.id, content="\n".join([*entries, summary]))


def _list_entries(path: Path, *, max_depth: int, limit: int) -> list[str]:
    if path.is_file() or path.is_symlink():
        return [str(path)]
    entries: list[str] = []
    _collect_entries(path, root=path, depth=0, max_depth=max_depth, limit=limit, entries=entries)
    return entries


def _collect_entries(
    path: Path,
    *,
    root: Path,
    depth: int,
    max_depth: int,
    limit: int,
    entries: list[str],
) -> None:
    if len(entries) >= limit:
        return
    children = sorted(path.iterdir(), key=lambda child: (not child.is_dir(), child.name.lower()))
    for child in children:
        if len(entries) >= limit:
            return
        is_dir = child.is_dir() and not child.is_symlink()
        if is_dir and child.name in _IGNORED_DIR_NAMES:
            continue
        entries.append(_display_path(child, root=root, is_dir=is_dir))
        if is_dir and depth < max_depth:
            _collect_entries(
                child,
                root=root,
                depth=depth + 1,
                max_depth=max_depth,
                limit=limit,
                entries=entries,
            )


def _display_path(path: Path, *, root: Path, is_dir: bool) -> str:
    display = str(path.relative_to(root))
    if is_dir:
        return f"{display}/"
    return display
