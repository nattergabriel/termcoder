"""Config loading — TOML files with precedence.

Precedence: per-project `.termcoder.toml` (cwd) > user-level config.toml >
built-in defaults. Secrets (API keys, base URL) live in env vars, never here.
Unknown keys in the TOML are ignored so the format can grow without breaking
older clients; type-mismatched values raise `ConfigError`.

`save_setting(...)` writes a single key back to a TOML file (used by slash
commands like `/model` so changes outlive the session). Comments and blank
lines in the file are dropped on rewrite — a v0.1 simplification.
"""

import json
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import platformdirs

from termcoder.errors import TermcoderError

type TomlScalar = str | int | float | bool

type PermissionMode = Literal["ask_each"]


class ConfigError(TermcoderError):
    """Raised when a config file has a value of the wrong type or shape."""


@dataclass(frozen=True, slots=True)
class Config:
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int | None = None
    system_prompt: str | None = None
    permission_mode: PermissionMode = "ask_each"


def load_config(
    *,
    cwd: Path | None = None,
    user_config_path: Path | None = None,
) -> Config:
    """Merge the user and project TOML files over the defaults and return a `Config`.

    `cwd` and `user_config_path` are injectable to keep tests away from real
    home directories; production calls pass neither.
    """
    user_path = user_config_path or default_user_config_path()
    project_path = (cwd or Path.cwd()) / ".termcoder.toml"

    merged: dict[str, Any] = {}
    for path in (user_path, project_path):
        if path.is_file():
            with path.open("rb") as f:
                merged.update(tomllib.load(f))
    return _from_dict(merged)


def default_user_config_path() -> Path:
    return Path(platformdirs.user_config_dir("termcoder")) / "config.toml"


def save_setting(key: str, value: TomlScalar, *, path: Path) -> None:
    """Write `key = value` to the TOML file at `path`, preserving other keys.

    Creates the file (and any missing parent directories) if needed. Comments
    and blank lines in the existing file are not preserved.
    """
    raw: dict[str, Any] = {}
    if path.is_file():
        with path.open("rb") as f:
            raw = tomllib.load(f)
    raw[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_serialize_toml(raw), encoding="utf-8")


def _from_dict(raw: Mapping[str, Any]) -> Config:
    defaults = Config()
    max_tokens_raw = raw.get("max_tokens", defaults.max_tokens)
    system_prompt_raw = raw.get("system_prompt", defaults.system_prompt)
    return Config(
        model=_as_str(raw.get("model", defaults.model), "model"),
        temperature=_as_float(raw.get("temperature", defaults.temperature), "temperature"),
        max_tokens=None if max_tokens_raw is None else _as_int(max_tokens_raw, "max_tokens"),
        system_prompt=(
            None if system_prompt_raw is None else _as_str(system_prompt_raw, "system_prompt")
        ),
        permission_mode=_as_permission_mode(raw.get("permission_mode", defaults.permission_mode)),
    )


def _as_str(value: object, field: str) -> str:
    if isinstance(value, str):
        return value
    raise ConfigError(f"{field} must be a string, got {type(value).__name__}")


def _as_float(value: object, field: str) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    raise ConfigError(f"{field} must be a number, got {type(value).__name__}")


def _as_int(value: object, field: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ConfigError(f"{field} must be an integer, got {type(value).__name__}")


def _as_permission_mode(value: object) -> PermissionMode:
    if value == "ask_each":
        return "ask_each"
    raise ConfigError(f"unknown permission_mode: {value!r}")


def _serialize_toml(data: Mapping[str, Any]) -> str:
    return "".join(f"{key} = {_format_value(value, key)}\n" for key, value in data.items())


def _format_value(value: object, field: str) -> str:
    # bool is a subclass of int — check it first.
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        # JSON basic strings are a valid subset of TOML basic strings.
        return json.dumps(value)
    if isinstance(value, int | float):
        return repr(value)
    raise ConfigError(f"cannot serialize {field}: unsupported type {type(value).__name__}")
