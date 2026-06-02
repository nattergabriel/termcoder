"""Config loading from TOML and environment defaults.

Precedence: per-project `.termcoder.toml` (cwd) > user-level config.toml >
built-in defaults. Secrets (API keys, base URL) live in env vars, never here.
Unknown keys are ignored; type mismatches raise `ConfigError`.
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

type PermissionMode = Literal["ask_each", "allow_readonly", "allow_all"]
type ProviderName = Literal["openai", "anthropic"]
type ChannelName = Literal["terminal"]

_PERMISSION_MODES: frozenset[PermissionMode] = frozenset(
    ("ask_each", "allow_readonly", "allow_all")
)
_PROVIDER_NAMES: frozenset[ProviderName] = frozenset(("openai", "anthropic"))
_CHANNEL_NAMES: frozenset[ChannelName] = frozenset(("terminal",))


class ConfigError(TermcoderError):
    """Raised when a config file has a value of the wrong type or shape."""


@dataclass(frozen=True, slots=True)
class Config:
    provider: ProviderName = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int | None = None
    system_prompt: str | None = None
    permission_mode: PermissionMode = "ask_each"
    max_iterations: int = 25
    channel: ChannelName = "terminal"


def load_config(
    *,
    cwd: Path | None = None,
    user_config_path: Path | None = None,
) -> Config:
    """Merge user and project TOML files over the defaults."""
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
    """Write one top-level TOML key, preserving other keys."""
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
        provider=_as_provider(raw.get("provider", defaults.provider)),
        model=_as_str(raw.get("model", defaults.model), "model"),
        temperature=_as_float(raw.get("temperature", defaults.temperature), "temperature"),
        max_tokens=None if max_tokens_raw is None else _as_int(max_tokens_raw, "max_tokens"),
        system_prompt=(
            None if system_prompt_raw is None else _as_str(system_prompt_raw, "system_prompt")
        ),
        permission_mode=_as_permission_mode(raw.get("permission_mode", defaults.permission_mode)),
        max_iterations=_as_int(
            raw.get("max_iterations", defaults.max_iterations), "max_iterations"
        ),
        channel=_as_channel(raw.get("channel", defaults.channel)),
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
    if value in _PERMISSION_MODES:
        return value
    raise ConfigError(f"unknown permission_mode: {value!r}")


def _as_provider(value: object) -> ProviderName:
    if value in _PROVIDER_NAMES:
        return value
    raise ConfigError(f"unknown provider: {value!r}")


def _as_channel(value: object) -> ChannelName:
    if value in _CHANNEL_NAMES:
        return value
    raise ConfigError(f"unknown channel: {value!r}")


def _serialize_toml(data: Mapping[str, Any]) -> str:
    return "".join(f"{key} = {_format_value(value, key)}\n" for key, value in data.items())


def _format_value(value: object, field: str) -> str:
    # bool is a subclass of int; check it first.
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        # JSON strings are valid TOML basic strings.
        return json.dumps(value)
    if isinstance(value, int | float):
        return repr(value)
    raise ConfigError(f"cannot serialize {field}: unsupported type {type(value).__name__}")
