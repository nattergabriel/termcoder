"""Tests for shared tool argument parsing helpers."""

import json

import pytest

from termcoder.models import ToolCall
from termcoder.tools.arguments import (
    ArgumentError,
    optional_bool,
    optional_int,
    parse_object,
    required_string,
)


def test_parse_object_returns_json_object() -> None:
    call = _call({"path": "example.txt"})

    assert parse_object(call) == {"path": "example.txt"}


def test_parse_object_rejects_malformed_json() -> None:
    with pytest.raises(ArgumentError, match="Expecting value"):
        parse_object(ToolCall(id="c1", name="read", arguments="not json"))


def test_parse_object_rejects_non_object_json() -> None:
    with pytest.raises(ArgumentError, match="JSON object"):
        parse_object(ToolCall(id="c1", name="read", arguments='["path"]'))


def test_required_string_returns_value() -> None:
    assert required_string({"path": "example.txt"}, "path") == "example.txt"


def test_required_string_rejects_missing_key() -> None:
    with pytest.raises(ArgumentError, match="path"):
        required_string({}, "path")


def test_required_string_rejects_non_string_value() -> None:
    with pytest.raises(ArgumentError, match="path"):
        required_string({"path": 123}, "path")


def test_optional_int_returns_none_when_missing() -> None:
    assert optional_int({}, "limit") is None


def test_optional_int_returns_integer_value() -> None:
    assert optional_int({"limit": 10}, "limit") == 10


def test_optional_int_rejects_bool() -> None:
    with pytest.raises(ArgumentError, match="limit"):
        optional_int({"limit": True}, "limit")


def test_optional_int_rejects_non_integer() -> None:
    with pytest.raises(ArgumentError, match="limit"):
        optional_int({"limit": "10"}, "limit")


def test_optional_bool_returns_default_when_missing() -> None:
    assert optional_bool({}, "replace_all", default=True) is True


def test_optional_bool_returns_bool_value() -> None:
    assert optional_bool({"replace_all": False}, "replace_all", default=True) is False


def test_optional_bool_rejects_non_bool() -> None:
    with pytest.raises(ArgumentError, match="replace_all"):
        optional_bool({"replace_all": "yes"}, "replace_all", default=False)


def _call(args: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name="read", arguments=json.dumps(args))
