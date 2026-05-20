"""Prompt history for the main user input."""

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent


class PromptHistory:
    """Small in-memory history navigated with Up/Down."""

    def __init__(self, session: PromptSession[str]) -> None:
        self._session = session
        self.entries: list[str] = []
        self.index: int | None = None

    def key_bindings(self) -> KeyBindings:
        bindings = KeyBindings()

        @bindings.add("up")
        def history_previous(event: KeyPressEvent) -> None:
            del event
            self.previous()

        @bindings.add("down")
        def history_next(event: KeyPressEvent) -> None:
            del event
            self.next()

        return bindings

    def reset_navigation(self) -> None:
        self.index = None

    def append(self, text: str) -> None:
        self.entries.append(text)

    def previous(self) -> None:
        if not self.entries:
            return
        if self.index is None:
            self.index = len(self.entries) - 1
        else:
            self.index = max(0, self.index - 1)
        self._set_prompt_text(self.entries[self.index])

    def next(self) -> None:
        if self.index is None:
            return
        if self.index >= len(self.entries) - 1:
            self.index = None
            self._set_prompt_text("")
            return
        self.index += 1
        self._set_prompt_text(self.entries[self.index])

    def _set_prompt_text(self, text: str) -> None:
        buffer = self._session.default_buffer
        buffer.text = text
        buffer.cursor_position = len(text)
