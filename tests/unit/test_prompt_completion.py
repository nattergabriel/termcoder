"""Unit tests for prompt autocomplete."""

from pathlib import Path

from prompt_toolkit.completion import CompleteEvent, Completion
from prompt_toolkit.document import Document

from termcoder.skills import Skill, SkillCatalog
from termcoder.ui.completion import PromptCompleter


def _complete(text: str, completer: PromptCompleter) -> list[Completion]:
    return list(completer.get_completions(Document(text), CompleteEvent()))


def _skill_catalog(tmp_path: Path) -> SkillCatalog:
    location = tmp_path / "python-testing" / "SKILL.md"
    location.parent.mkdir()
    location.write_text("", encoding="utf-8")
    return SkillCatalog(
        (
            Skill(
                name="python-testing",
                description="Write Python tests.",
                location=location,
                body="Use pytest.",
            ),
            Skill(
                name="review",
                description="Review code.",
                location=location,
                body="Review carefully.",
            ),
        )
    )


def test_completes_commands_at_prompt_start(tmp_path: Path) -> None:
    completer = PromptCompleter(
        command_names=("model", "provider"),
        skills=_skill_catalog(tmp_path),
    )

    completions = _complete("/mo", completer)

    assert [completion.text for completion in completions] == ["/model"]
    assert completions[0].start_position == -3


def test_completes_skills_at_prompt_start(tmp_path: Path) -> None:
    completer = PromptCompleter(command_names=(), skills=_skill_catalog(tmp_path))

    completions = _complete("/python", completer)

    assert [completion.text for completion in completions] == ["/python-testing"]
    assert completions[0].display_meta_text == "Write Python tests."


def test_does_not_complete_commands_mid_prompt(tmp_path: Path) -> None:
    completer = PromptCompleter(
        command_names=("model",),
        skills=_skill_catalog(tmp_path),
    )

    completions = _complete("please use /mo", completer)

    assert [completion.text for completion in completions] == []


def test_completes_skills_mid_prompt(tmp_path: Path) -> None:
    completer = PromptCompleter(
        command_names=("model",),
        skills=_skill_catalog(tmp_path),
    )

    completions = _complete("please use /py", completer)

    assert [completion.text for completion in completions] == ["/python-testing"]


def test_does_not_complete_slash_after_word_character(tmp_path: Path) -> None:
    completer = PromptCompleter(
        command_names=("model",),
        skills=_skill_catalog(tmp_path),
    )

    completions = _complete("path/to /py", completer)

    assert [completion.text for completion in completions] == ["/python-testing"]
    assert _complete("path/to/py", completer) == []


def test_skips_skill_duplicate_when_command_name_wins_at_prompt_start(tmp_path: Path) -> None:
    completer = PromptCompleter(
        command_names=("review",),
        skills=_skill_catalog(tmp_path),
    )

    completions = _complete("/re", completer)

    assert [completion.text for completion in completions] == ["/review"]
    assert completions[0].display_meta_text == "command"
