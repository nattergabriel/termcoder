"""Tests for the tool Registry."""

from termcoder.tools.delete import Delete
from termcoder.tools.edit import Edit
from termcoder.tools.list_files import ListFiles
from termcoder.tools.move import Move
from termcoder.tools.patch import Patch
from termcoder.tools.read import Read
from termcoder.tools.registry import Registry
from termcoder.tools.search import Search
from termcoder.tools.write import Write


def test_init_indexes_tools_by_schema_name() -> None:
    registry = Registry(
        [
            Read(),
            Write(),
            Edit(),
            Search(),
            Patch(),
            ListFiles(),
            Move(),
            Delete(),
        ]
    )

    assert registry.get("read").__class__ is Read
    assert registry.get("write").__class__ is Write
    assert registry.get("edit").__class__ is Edit
    assert registry.get("search").__class__ is Search
    assert registry.get("patch").__class__ is Patch
    assert registry.get("list_files").__class__ is ListFiles
    assert registry.get("move").__class__ is Move
    assert registry.get("delete").__class__ is Delete


def test_get_returns_none_for_unknown_tool() -> None:
    registry = Registry([Read()])

    assert registry.get("nonexistent") is None


def test_schemas_returns_each_tools_schema() -> None:
    read, write = Read(), Write()
    registry = Registry([read, write])

    assert list(registry.schemas()) == [read.schema, write.schema]


def test_empty_registry_has_no_schemas() -> None:
    assert Registry().schemas() == ()
