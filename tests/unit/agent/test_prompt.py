"""Unit tests for system-prompt assembly."""

from pathlib import Path

from termcoder.agent.prompt import DEFAULT_SYSTEM_PROMPT, assemble_system_prompt
from termcoder.instructions import InstructionFile


def test_default_when_no_custom_instructions() -> None:
    assert assemble_system_prompt() == DEFAULT_SYSTEM_PROMPT


def test_empty_custom_instructions_treated_as_none() -> None:
    assert assemble_system_prompt("") == DEFAULT_SYSTEM_PROMPT


def test_appends_custom_instructions_with_blank_line() -> None:
    assert (
        assemble_system_prompt("Always cite filenames.")
        == f"{DEFAULT_SYSTEM_PROMPT}\n\nAlways cite filenames."
    )


def test_appends_agent_instruction_files_before_custom_instructions() -> None:
    prompt = assemble_system_prompt(
        "Always cite filenames.",
        instruction_files=(
            InstructionFile(path=Path("/repo/AGENTS.md"), content="Run tests."),
            InstructionFile(path=Path("/repo/pkg/AGENTS.md"), content="Use strict types."),
        ),
    )

    assert prompt == (
        f"{DEFAULT_SYSTEM_PROMPT}\n\n"
        "Project instructions from AGENTS.md files follow. "
        "They are ordered from broadest scope to nearest cwd; later files override "
        "earlier files when instructions conflict.\n\n"
        "/repo/AGENTS.md:\nRun tests.\n\n"
        "/repo/pkg/AGENTS.md:\nUse strict types.\n\n"
        "Always cite filenames."
    )
