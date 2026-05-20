"""Arrow-key choice prompt input handling."""

import asyncio
from collections.abc import Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.input import Input
from prompt_toolkit.input.typeahead import get_typeahead, store_typeahead
from prompt_toolkit.key_binding.key_processor import KeyPress
from prompt_toolkit.keys import Keys

from termcoder.ui.interaction import ChoicePromptState


class ChoiceReader:
    """Read a single selection from the prompt-toolkit input stream."""

    def __init__(
        self,
        session: PromptSession[str],
        refresh: Callable[[], None],
    ) -> None:
        self._session = session
        self._refresh = refresh

    async def read(self, state: ChoicePromptState) -> None:
        queue: asyncio.Queue[KeyPress] = asyncio.Queue()
        prompt_input = self._session.input

        def input_ready() -> None:
            for key_press in prompt_input.read_keys():
                queue.put_nowait(key_press)

        for key_press in get_typeahead(prompt_input):
            queue.put_nowait(key_press)
        with prompt_input.raw_mode(), prompt_input.attach(input_ready):
            input_ready()
            while True:
                key_press = await queue.get()
                if self.apply_key(state, key_press):
                    self.store_leftovers(prompt_input, queue)
                    return

    def store_leftovers(
        self,
        prompt_input: Input,
        queue: asyncio.Queue[KeyPress],
    ) -> None:
        leftovers: list[KeyPress] = []
        while not queue.empty():
            leftovers.append(queue.get_nowait())
        if leftovers:
            store_typeahead(prompt_input, leftovers)

    def apply_key(self, state: ChoicePromptState, key_press: KeyPress) -> bool:
        key = key_press.key
        if key in {Keys.ControlC, Keys.ControlD, Keys.Escape}:
            raise asyncio.CancelledError
        if key in {Keys.Up, Keys.ControlP, Keys.BackTab}:
            self.move(state, -1)
            return False
        if key in {Keys.Down, Keys.ControlN, Keys.ControlI}:
            self.move(state, 1)
            return False
        if key in {Keys.ControlJ, Keys.ControlM}:
            return True
        if isinstance(key, str):
            self.select_shortcut(state, key.lower())
        return False

    def select_shortcut(self, state: ChoicePromptState, key: str) -> None:
        for index, option in enumerate(state.prompt.options):
            if option.shortcut is not None and option.shortcut.lower() == key:
                state.selected_index = index
                self._refresh()
                return
            if str(index + 1) == key:
                state.selected_index = index
                self._refresh()
                return

    def move(self, state: ChoicePromptState, offset: int) -> None:
        state.selected_index = (state.selected_index + offset) % len(state.prompt.options)
        self._refresh()
