"""Prompt completions for user input."""

import re
from collections.abc import Iterator, Sequence

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

from termcoder.skills import SkillCatalog

_SLASH_TOKEN_AT_CURSOR = re.compile(r"(?<!\w)/([A-Za-z0-9_.-]*)$")


class PromptCompleter(Completer):
    """Complete slash commands at prompt start and skill tokens anywhere."""

    def __init__(
        self,
        *,
        command_names: Sequence[str],
        skills: SkillCatalog | None,
    ) -> None:
        self._command_names = tuple(command_names)
        self._skills = skills

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
    ) -> Iterator[Completion]:
        del complete_event

        text = document.text_before_cursor
        match = _SLASH_TOKEN_AT_CURSOR.search(text)
        if match is None:
            return

        typed = match.group(1)
        start_position = match.start() - len(text)

        if text[: match.start()].strip() == "":
            command_names = set(self._command_names)
            yield from _matching_completions(
                typed=typed,
                start_position=start_position,
                entries=((name, "command") for name in self._command_names),
            )
        else:
            command_names = set()

        if self._skills is not None:
            yield from _matching_completions(
                typed=typed,
                start_position=start_position,
                entries=(
                    (skill.name, skill.description)
                    for skill in self._skills.skills
                    if skill.name not in command_names
                ),
            )


def _matching_completions(
    *,
    typed: str,
    start_position: int,
    entries: Iterator[tuple[str, str]],
) -> Iterator[Completion]:
    for name, meta in entries:
        if name.startswith(typed):
            yield Completion(f"/{name}", start_position=start_position, display_meta=meta)
