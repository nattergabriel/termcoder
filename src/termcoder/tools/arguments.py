"""Helpers for parsing JSON tool-call arguments."""

import json
from collections.abc import Mapping

from termcoder.models import ToolCall


class ArgumentError(ValueError):
    """User-facing tool argument error."""


def parse_object(call: ToolCall) -> Mapping[str, object]:
    """Parse `call.arguments` as a JSON object."""
    try:
        raw = json.loads(call.arguments)
    except json.JSONDecodeError as exc:
        raise ArgumentError(str(exc)) from exc
    if not isinstance(raw, dict):
        raise ArgumentError("arguments must be a JSON object")
    return raw


def required_string(args: Mapping[str, object], key: str) -> str:
    """Return a required string argument by key."""
    try:
        value = args[key]
    except KeyError as exc:
        raise ArgumentError(str(exc)) from exc
    if not isinstance(value, str):
        raise ArgumentError(f"{key!r} must be a string")
    return value


def optional_string(args: Mapping[str, object], key: str) -> str | None:
    """Return an optional string argument by key."""
    if key not in args:
        return None
    value = args[key]
    if not isinstance(value, str):
        raise ArgumentError(f"{key!r} must be a string")
    return value


def optional_int(args: Mapping[str, object], key: str) -> int | None:
    """Return an optional integer argument by key."""
    if key not in args:
        return None
    value = args[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArgumentError(f"{key!r} must be an integer")
    return value


def optional_bool(args: Mapping[str, object], key: str, *, default: bool) -> bool:
    """Return an optional boolean argument by key."""
    if key not in args:
        return default
    value = args[key]
    if not isinstance(value, bool):
        raise ArgumentError(f"{key!r} must be a boolean")
    return value
