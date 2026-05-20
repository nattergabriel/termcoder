"""Small formatting helpers shared by terminal UI renderers."""

import json
from collections.abc import Sequence

from termcoder.models import PermissionDecision, ToolCall, ToolResult
from termcoder.ui.interaction import ChoiceOption, ChoicePrompt


def permission_prompt(call: ToolCall) -> ChoicePrompt[PermissionDecision]:
    """Build the permission prompt shown before running a tool."""
    return ChoicePrompt(
        title=f"Allow {tool_summary(call)}?",
        options=(
            ChoiceOption(label="Yes", value="allow", shortcut="y"),
            ChoiceOption(label="No", value="deny", shortcut="n"),
        ),
        default_index=1,
    )


def tool_summary(call: ToolCall) -> str:
    summary = tool_display_name(call.name)
    preview = argument_preview(call.arguments)
    if not preview:
        return summary
    return f"{summary}({preview})"


def tool_display_name(name: str) -> str:
    return name.replace("_", " ").title().replace(" ", "")


def argument_preview(arguments: str) -> str:
    try:
        parsed: object = json.loads(arguments)
    except json.JSONDecodeError:
        return single_line_preview(arguments)

    if not isinstance(parsed, dict):
        return single_line_preview(arguments)

    command = parsed.get("command")
    if isinstance(command, str):
        return single_line_preview(command)

    path = parsed.get("path")
    if isinstance(path, str):
        content = parsed.get("content")
        if isinstance(content, str):
            return single_line_preview(f"{path}, {character_count(content)}")
        return single_line_preview(path)

    return single_line_preview(arguments)


def single_line_preview(content: str) -> str:
    preview = " ".join(content.splitlines()).strip()
    if len(preview) <= 120:
        return preview
    return preview[:117] + "..."


def line_preview(content: str, *, max_lines: int, preserve_tail: bool = False) -> str:
    lines = content.splitlines()
    if len(lines) <= max_lines:
        return content
    hidden = len(lines) - max_lines
    if preserve_tail and max_lines >= 3:
        head_count = max_lines - 2
        hidden = len(lines) - head_count - 1
        return "\n".join([*lines[:head_count], hidden_line(hidden), lines[-1]])
    return "\n".join([*lines[:max_lines], hidden_line(hidden)])


def tool_result_heading(call: ToolCall | None, result: ToolResult) -> str:
    label = tool_result_label(call, result)
    if call is None:
        return label
    return f"{tool_summary(call)}: {label}"


def tool_result_label(call: ToolCall | None, result: ToolResult) -> str:
    if result.is_error:
        if "denied permission" in result.content.lower():
            return "Denied"
        return "Failed"
    if call is not None and call.name == "read":
        count = len(result.content.splitlines())
        return f"Read {pluralize(count, 'line')}"
    return "Done"


def slash_command_summary(command_names: Sequence[str]) -> str:
    return " ".join(f"/{name}" for name in command_names)


def character_count(content: str) -> str:
    return pluralize(len(content), "character")


def hidden_line(count: int) -> str:
    noun = "line" if count == 1 else "lines"
    return f"... {count} more {noun}"


def pluralize(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"


def prefix_lines(content: str, *, first: str, rest: str) -> str:
    lines = content.splitlines(keepends=True)
    if not lines:
        return first
    prefixed: list[str] = []
    for index, line in enumerate(lines):
        prefix = first if index == 0 else rest
        prefixed.append(prefix + line)
    return "".join(prefixed)
