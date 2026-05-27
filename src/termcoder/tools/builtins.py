"""Built-in tool registration."""

from termcoder.tools.bash import Bash
from termcoder.tools.delete import Delete
from termcoder.tools.edit import Edit
from termcoder.tools.list_files import ListFiles
from termcoder.tools.move import Move
from termcoder.tools.protocol import Tool
from termcoder.tools.read import Read
from termcoder.tools.search import Search
from termcoder.tools.write import Write


def builtin_tools() -> tuple[Tool, ...]:
    return (
        Read(),
        Write(),
        Edit(),
        Bash(),
        Search(),
        ListFiles(),
        Move(),
        Delete(),
    )
