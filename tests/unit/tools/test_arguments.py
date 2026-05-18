"""Tests for shared tool argument parsing helpers."""

import json

import pytest

from termcoder.models import ToolCall
from termcoder.tools.arguments import ArgumentError, parse_object, required_string


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


def _call(args: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name="read", arguments=json.dumps(args))
