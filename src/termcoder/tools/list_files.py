"""List files tool."""

from collections import deque
from pathlib import Path

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, ToolArgs
from termcoder.tools.filesystem import display_path, is_ignored_dir, path_arg, sorted_children
from termcoder.tools.protocol import ToolPermission
from termcoder.tools.results import invalid_arguments, tool_failed, tool_ok

_DEFAULT_MAX_DEPTH = 2
_DEFAULT_LIMIT = 200


class ListFiles:
    permission: ToolPermission = "readonly"
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
            args = ToolArgs.from_call(call)
            path = path_arg(args, "path")
            max_depth = args.int("max_depth", default=_DEFAULT_MAX_DEPTH, minimum=0)
            limit = args.int("limit", default=_DEFAULT_LIMIT, minimum=1)
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        try:
            entries = _list_entries(path, max_depth=max_depth, limit=limit)
        except OSError as exc:
            return tool_failed(call, "list_files", exc)

        if not entries:
            return tool_ok(call, f"no entries under {path}")
        summary = f"listed {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"
        if len(entries) >= limit:
            summary += f"; showing first {limit}"
        return tool_ok(call, "\n".join([*entries, summary]))


def _list_entries(path: Path, *, max_depth: int, limit: int) -> list[str]:
    if path.is_file() or path.is_symlink():
        return [str(path)]

    entries: list[str] = []
    queue: deque[tuple[Path, int]] = deque((child, 0) for child in sorted_children(path))
    while queue and len(entries) < limit:
        child, depth = queue.popleft()
        is_dir = child.is_dir() and not child.is_symlink()
        if is_dir and is_ignored_dir(child):
            continue
        entries.append(display_path(child, path, is_dir=is_dir))
        if is_dir and depth < max_depth:
            queue.extend((grandchild, depth + 1) for grandchild in sorted_children(child))
    return entries
