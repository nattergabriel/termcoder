"""Unit tests for TOML config loading.

Real files in `tmp_path` — no mocked I/O. Covers defaults, single-source loads,
the project > user > defaults precedence chain, unknown-key tolerance, and
type-error surfacing.
"""

from pathlib import Path

import pytest

from termcoder.config import Config, ConfigError, load_config


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_defaults_when_no_files_present(tmp_path: Path) -> None:
    config = load_config(cwd=tmp_path, user_config_path=tmp_path / "missing.toml")
    assert config == Config()


def test_user_config_overrides_defaults(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'model = "gpt-foo"\ntemperature = 0.1\n')

    config = load_config(cwd=tmp_path / "elsewhere", user_config_path=user_path)
    assert config.model == "gpt-foo"
    assert config.temperature == pytest.approx(0.1)


def test_project_config_overrides_user_config(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'model = "from-user"\ntemperature = 0.1\n')
    _write(tmp_path / ".termcoder.toml", 'model = "from-project"\n')

    config = load_config(cwd=tmp_path, user_config_path=user_path)
    assert config.model == "from-project"
    # Project file didn't set temperature, so user-config value carries through.
    assert config.temperature == pytest.approx(0.1)


def test_unknown_keys_are_ignored(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'model = "x"\nnonsense = true\n')

    config = load_config(cwd=tmp_path, user_config_path=user_path)
    assert config.model == "x"


def test_max_tokens_and_system_prompt_round_trip(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'max_tokens = 256\nsystem_prompt = "be terse"\n')

    config = load_config(cwd=tmp_path, user_config_path=user_path)
    assert config.max_tokens == 256
    assert config.system_prompt == "be terse"


def test_permission_mode_ask_each_parses(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'permission_mode = "ask_each"\n')

    config = load_config(cwd=tmp_path, user_config_path=user_path)
    assert config.permission_mode == "ask_each"


def test_unknown_permission_mode_raises(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'permission_mode = "yolo"\n')

    with pytest.raises(ConfigError, match="permission_mode"):
        load_config(cwd=tmp_path, user_config_path=user_path)


def test_provider_anthropic_parses(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'provider = "anthropic"\n')

    config = load_config(cwd=tmp_path, user_config_path=user_path)
    assert config.provider == "anthropic"


def test_unknown_provider_raises(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'provider = "cohere"\n')

    with pytest.raises(ConfigError, match="provider"):
        load_config(cwd=tmp_path, user_config_path=user_path)


def test_wrong_type_raises(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, "model = 42\n")

    with pytest.raises(ConfigError, match="model"):
        load_config(cwd=tmp_path, user_config_path=user_path)
