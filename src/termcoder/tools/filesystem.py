"""Shared filesystem helpers for tools."""

import os
from collections.abc import Iterator
from pathlib import Path

IGNORED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
}


def display_path(path: Path, root: Path, *, is_dir: bool = False) -> str:
    if root.is_file():
        return str(path)
    try:
        value = str(path.relative_to(root))
    except ValueError:
        value = str(path)
    return f"{value}/" if is_dir else value


def is_ignored_dir(path: Path) -> bool:
    return path.name in IGNORED_DIR_NAMES


def sorted_children(path: Path) -> list[Path]:
    return sorted(path.iterdir(), key=lambda child: (not child.is_dir(), child.name.lower()))


def iter_files(path: Path) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    for root, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(name for name in dirnames if name not in IGNORED_DIR_NAMES)
        for filename in sorted(filenames):
            candidate = Path(root) / filename
            if candidate.is_file():
                yield candidate
