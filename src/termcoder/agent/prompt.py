"""System-prompt assembly."""

from collections.abc import Sequence

from termcoder.instructions import InstructionFile

DEFAULT_SYSTEM_PROMPT = (
    "You are termcoder, a terminal-based coding assistant. "
    "Be concise, prefer small focused actions, and ask the user before destructive operations."
)


def assemble_system_prompt(
    custom_instructions: str | None = None,
    *,
    instruction_files: Sequence[InstructionFile] = (),
) -> str:
    """Return the system prompt with optional project and user instructions."""
    parts = [DEFAULT_SYSTEM_PROMPT]
    if instruction_files:
        parts.append(_format_instruction_files(instruction_files))
    if not custom_instructions:
        return "\n\n".join(parts)
    parts.append(custom_instructions)
    return "\n\n".join(parts)


def _format_instruction_files(instruction_files: Sequence[InstructionFile]) -> str:
    sections = [
        "Project instructions from AGENTS.md files follow. "
        "They are ordered from broadest scope to nearest cwd; later files override "
        "earlier files when instructions conflict."
    ]
    for instruction_file in instruction_files:
        sections.append(f"{instruction_file.path}:\n{instruction_file.content}")
    return "\n\n".join(sections)
