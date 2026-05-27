"""Search tool."""

import re
from collections.abc import Callable
from pathlib import Path

from termcoder.models import ToolCall, ToolResult, ToolSchema
from termcoder.tools.arguments import ArgumentError, ToolArgs
from termcoder.tools.filesystem import display_path, iter_files
from termcoder.tools.results import invalid_arguments, tool_error, tool_ok

_DEFAULT_LIMIT = 50
_MAX_LINE_LENGTH = 240


class Search:
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
            args = ToolArgs.from_call(call)
            path = args.required_path("path")
            query = args.required_string("query")
            regex = args.bool("regex", default=False)
            case_sensitive = args.bool("case_sensitive", default=True)
            limit = args.int("limit", default=_DEFAULT_LIMIT, minimum=1)
            if query == "":
                raise ArgumentError("'query' must not be empty")
            matcher = _line_matcher(query, regex=regex, case_sensitive=case_sensitive)
        except ArgumentError as exc:
            return invalid_arguments(call, exc)

        if not path.exists():
            return tool_error(call, f"search failed: {path} does not exist")

        matches: list[str] = []
        files_searched = 0
        files_skipped = 0
        for file_path in iter_files(path):
            try:
                file_matches = _search_file(
                    file_path,
                    root=path,
                    matcher=matcher,
                    remaining=limit - len(matches),
                )
            except (OSError, UnicodeDecodeError):
                files_skipped += 1
                continue
            files_searched += 1
            matches.extend(file_matches)
            if len(matches) >= limit:
                break

        return tool_ok(call, _format_results(matches, files_searched, files_skipped, limit))


def _line_matcher(query: str, *, regex: bool, case_sensitive: bool) -> Callable[[str], bool]:
    if not regex:
        if case_sensitive:
            return lambda line: query in line
        folded_query = query.lower()
        return lambda line: folded_query in line.lower()

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query, flags)
    except re.error as exc:
        raise ArgumentError(f"invalid regex: {exc}") from exc

    return lambda line: pattern.search(line) is not None


def _search_file(
    file_path: Path,
    *,
    root: Path,
    matcher: Callable[[str], bool],
    remaining: int,
) -> list[str]:
    matches: list[str] = []
    shown_path = display_path(file_path, root)
    with file_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.rstrip("\r\n")
            if matcher(line):
                matches.append(f"{shown_path}:{line_number}: {_truncate(line)}")
                if len(matches) >= remaining:
                    break
    return matches


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
