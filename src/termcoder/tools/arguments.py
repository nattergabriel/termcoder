"""Helpers for parsing JSON tool-call arguments."""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from termcoder.models import ToolCall


class ArgumentError(ValueError):
    """User-facing tool argument error."""


@dataclass(frozen=True, slots=True)
class ToolArgs:
    """Typed access to a tool call's JSON object arguments."""

    values: Mapping[str, object]

    @classmethod
    def from_call(cls, call: ToolCall) -> "ToolArgs":
        try:
            raw = json.loads(call.arguments)
        except json.JSONDecodeError as exc:
            raise ArgumentError(str(exc)) from exc
        if not isinstance(raw, dict):
            raise ArgumentError("arguments must be a JSON object")
        return cls(raw)

    def required_string(self, key: str) -> str:
        try:
            value = self.values[key]
        except KeyError as exc:
            raise ArgumentError(f"missing required argument: {key}") from exc
        if not isinstance(value, str):
            raise ArgumentError(f"{key!r} must be a string")
        return value

    def optional_string(self, key: str) -> str | None:
        if key not in self.values:
            return None
        value = self.values[key]
        if not isinstance(value, str):
            raise ArgumentError(f"{key!r} must be a string")
        return value

    def optional_int(self, key: str, *, minimum: int | None = None) -> int | None:
        if key not in self.values:
            return None
        value = self.values[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ArgumentError(f"{key!r} must be an integer")
        _check_minimum(key, value, minimum)
        return value

    def int(self, key: str, *, default: int, minimum: int | None = None) -> int:
        value = self.optional_int(key, minimum=minimum)
        return default if value is None else value

    def bool(self, key: str, *, default: bool) -> bool:
        if key not in self.values:
            return default
        value = self.values[key]
        if not isinstance(value, bool):
            raise ArgumentError(f"{key!r} must be a boolean")
        return value


def _check_minimum(key: str, value: int, minimum: int | None) -> None:
    if minimum is not None and value < minimum:
        raise ArgumentError(f"{key!r} must be at least {minimum}")
