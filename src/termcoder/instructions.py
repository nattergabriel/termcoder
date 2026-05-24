"""Project instruction file loading."""

from dataclasses import dataclass
from pathlib import Path

_INSTRUCTION_FILENAME = "AGENTS.md"


@dataclass(frozen=True, slots=True)
class InstructionFile:
    """A loaded project instruction file."""

    path: Path
    content: str


def load_agent_instruction_files(cwd: Path | None = None) -> tuple[InstructionFile, ...]:
    """Load AGENTS.md files from cwd and its parent hierarchy.

    Files are ordered from broadest scope to nearest cwd so more specific
    instructions appear later in the prompt.
    """
    start = (cwd or Path.cwd()).resolve()
    if not start.is_dir():
        start = start.parent

    files: list[InstructionFile] = []
    for directory in _instruction_directories(start):
        path = directory / _INSTRUCTION_FILENAME
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        if content.strip():
            files.append(InstructionFile(path=path, content=content))
    return tuple(files)


def _instruction_directories(cwd: Path) -> tuple[Path, ...]:
    candidates = (cwd, *cwd.parents)
    return tuple(reversed(candidates))
