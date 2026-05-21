"""Search tool."""

import os
import re
from collections.abc import Iterator
from pathlib import Path

from termcoder.models import ToolCall, ToolName, ToolResult, ToolSchema
from termcoder.tools.arguments import (
    ArgumentError,
    optional_bool,
    optional_int,
    parse_object,
    required_string,
)
from termcoder.tools.results import invalid_arguments, tool_error

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
_DEFAULT_LIMIT = 50
_MAX_LINE_LENGTH = 240


class Search:
    name: ToolName = "search"
    schema: ToolSchema = ToolSchema(
        name="search",
        description=(
            "Search UTF-8 text files under a file or directory. Returns matching lines with "
            "1-based line numbers."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory to search.",
                },
                "query": {
                    "type": "string",
                    "description": "Text or regular expression to search for. Must not be empty.",
                },
                "regex": {
                    "type": "boolean",
                    "description": "Treat query as a Python regular expression when true.",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Use case-sensitive matching. Defaults to true.",
                },
                "limit": {
                    "type": "integer",
                    "description": (
                        f"Maximum matching lines to return. Defaults to {_DEFAULT_LIMIT}."
                    ),
                },
            },
            "required": ["path", "query"],
        },
    )

    async def run(self, call: ToolCall) -> ToolResult:
        try:
            args = parse_object(call)
            path = Path(required_string(args, "path"))
            query = required_string(args, "query")
            regex = optional_bool(args, "regex", default=False)
            case_sensitive = optional_bool(args, "case_sensitive", default=True)
            requested_limit = optional_int(args, "limit")
            limit = _DEFAULT_LIMIT if requested_limit is None else requested_limit
            if query == "":
                raise ArgumentError("'query' must not be empty")
            if limit < 1:
                raise ArgumentError("'limit' must be at least 1")
            pattern = _compile_pattern(query, regex=regex, case_sensitive=case_sensitive)
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        if not path.exists():
            return tool_error(call, f"search failed: {path} does not exist")

        matches: list[str] = []
        files_searched = 0
        files_skipped = 0
        for file_path in _iter_files(path):
            try:
                file_matches = _search_file(
                    file_path,
                    root=path,
                    query=query,
                    pattern=pattern,
                    case_sensitive=case_sensitive,
                    remaining=limit - len(matches),
                )
            except (OSError, UnicodeDecodeError):
                files_skipped += 1
                continue
            files_searched += 1
            matches.extend(file_matches)
            if len(matches) >= limit:
                return ToolResult(
                    tool_call_id=call.id,
                    content=_format_results(matches, files_searched, files_skipped, limit),
                )

        return ToolResult(
            tool_call_id=call.id,
            content=_format_results(matches, files_searched, files_skipped, limit),
        )


def _compile_pattern(query: str, *, regex: bool, case_sensitive: bool) -> re.Pattern[str] | None:
    if not regex:
        return None
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(query, flags)
    except re.error as exc:
        raise ArgumentError(f"invalid regex: {exc}") from exc


def _search_file(
    file_path: Path,
    *,
    root: Path,
    query: str,
    pattern: re.Pattern[str] | None,
    case_sensitive: bool,
    remaining: int,
) -> list[str]:
    matches: list[str] = []
    display_path = _display_path(file_path, root)
    with file_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.rstrip("\r\n")
            if _matches(line, query=query, pattern=pattern, case_sensitive=case_sensitive):
                matches.append(f"{display_path}:{line_number}: {_truncate(line)}")
                if len(matches) >= remaining:
                    break
    return matches


def _iter_files(path: Path) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    for root, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(name for name in dirnames if name not in _IGNORED_DIR_NAMES)
        for filename in sorted(filenames):
            candidate = Path(root) / filename
            if candidate.is_file():
                yield candidate


def _matches(
    line: str,
    *,
    query: str,
    pattern: re.Pattern[str] | None,
    case_sensitive: bool,
) -> bool:
    if pattern is not None:
        return pattern.search(line) is not None
    if case_sensitive:
        return query in line
    return query.lower() in line.lower()


def _display_path(file_path: Path, root: Path) -> str:
    if root.is_file():
        return str(file_path)
    try:
        return str(file_path.relative_to(root))
    except ValueError:
        return str(file_path)


def _truncate(line: str) -> str:
    if len(line) <= _MAX_LINE_LENGTH:
        return line
    return f"{line[: _MAX_LINE_LENGTH - 3]}..."


def _format_results(matches: list[str], files_searched: int, files_skipped: int, limit: int) -> str:
    summary = f"searched {files_searched} file(s)"
    if files_skipped:
        summary += f"; skipped {files_skipped} unreadable/non-UTF-8 file(s)"
    if not matches:
        return f"no matches\n{summary}"
    if len(matches) >= limit:
        summary += f"; showing first {limit} match(es)"
    else:
        summary += f"; found {len(matches)} match(es)"
    return "\n".join([*matches, summary])
