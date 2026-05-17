"""Unit tests for system-prompt assembly."""

from termcoder.agent.prompt import DEFAULT_SYSTEM_PROMPT, assemble_system_prompt


def test_default_when_no_custom_instructions() -> None:
    assert assemble_system_prompt() == DEFAULT_SYSTEM_PROMPT


def test_empty_custom_instructions_treated_as_none() -> None:
    assert assemble_system_prompt("") == DEFAULT_SYSTEM_PROMPT


def test_appends_custom_instructions_with_blank_line() -> None:
    assert (
        assemble_system_prompt("Always cite filenames.")
        == f"{DEFAULT_SYSTEM_PROMPT}\n\nAlways cite filenames."
    )
