"""Tests for shared tool argument parsing helpers."""

import json

import pytest

from termcoder.models import ToolCall
from termcoder.tools.arguments import ArgumentError, ToolArgs


def test_from_call_returns_json_object_args() -> None:
    args = ToolArgs.from_call(_call({"path": "example.txt"}))

    assert args.values == {"path": "example.txt"}


def test_from_call_rejects_malformed_json() -> None:
    with pytest.raises(ArgumentError, match="Expecting value"):
        ToolArgs.from_call(ToolCall(id="c1", name="read", arguments="not json"))


def test_from_call_rejects_non_object_json() -> None:
    with pytest.raises(ArgumentError, match="JSON object"):
        ToolArgs.from_call(ToolCall(id="c1", name="read", arguments='["path"]'))


def test_required_string_returns_value() -> None:
    args = ToolArgs({"path": "example.txt"})

    assert args.required_string("path") == "example.txt"


def test_required_string_rejects_missing_key() -> None:
    args = ToolArgs({})

    with pytest.raises(ArgumentError, match="missing required argument: path"):
        args.required_string("path")


def test_required_string_rejects_non_string_value() -> None:
    args = ToolArgs({"path": 123})

    with pytest.raises(ArgumentError, match="path"):
        args.required_string("path")


def test_optional_string_returns_none_when_missing() -> None:
    assert ToolArgs({}).optional_string("root") is None


def test_optional_string_returns_string_value() -> None:
    assert ToolArgs({"root": "."}).optional_string("root") == "."


def test_optional_int_returns_none_when_missing() -> None:
    assert ToolArgs({}).optional_int("limit") is None


def test_optional_int_returns_integer_value() -> None:
    assert ToolArgs({"limit": 10}).optional_int("limit") == 10


def test_optional_int_rejects_bool() -> None:
    with pytest.raises(ArgumentError, match="limit"):
        ToolArgs({"limit": True}).optional_int("limit")


def test_optional_int_rejects_values_below_minimum() -> None:
    with pytest.raises(ArgumentError, match="at least 1"):
        ToolArgs({"limit": 0}).optional_int("limit", minimum=1)


def test_int_returns_default_when_missing() -> None:
    assert ToolArgs({}).int("limit", default=50, minimum=1) == 50


def test_bool_returns_default_when_missing() -> None:
    assert ToolArgs({}).bool("replace_all", default=True) is True


def test_bool_returns_bool_value() -> None:
    assert ToolArgs({"replace_all": False}).bool("replace_all", default=True) is False


def test_bool_rejects_non_bool() -> None:
    with pytest.raises(ArgumentError, match="replace_all"):
        ToolArgs({"replace_all": "yes"}).bool("replace_all", default=False)


def _call(args: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name="read", arguments=json.dumps(args))
