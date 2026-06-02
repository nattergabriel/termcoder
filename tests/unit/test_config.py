"""Unit tests for TOML config loading.

Real files in `tmp_path` — no mocked I/O. Covers defaults, single-source loads,
the project > user > defaults precedence chain, unknown-key tolerance, and
type-error surfacing.
"""

from pathlib import Path

import pytest

from termcoder.config import Config, ConfigError, load_config, save_setting


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


def test_permission_mode_allow_all_parses(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'permission_mode = "allow_all"\n')

    config = load_config(cwd=tmp_path, user_config_path=user_path)
    assert config.permission_mode == "allow_all"


def test_permission_mode_allow_readonly_parses(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'permission_mode = "allow_readonly"\n')

    config = load_config(cwd=tmp_path, user_config_path=user_path)
    assert config.permission_mode == "allow_readonly"


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


def test_channel_terminal_parses(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'channel = "terminal"\n')

    config = load_config(cwd=tmp_path, user_config_path=user_path)
    assert config.channel == "terminal"


def test_channel_telegram_parses(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'channel = "telegram"\n')

    config = load_config(cwd=tmp_path, user_config_path=user_path)
    assert config.channel == "telegram"


def test_unknown_channel_raises(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'channel = "matrix"\n')

    with pytest.raises(ConfigError, match="channel"):
        load_config(cwd=tmp_path, user_config_path=user_path)


def test_wrong_type_raises(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, "model = 42\n")

    with pytest.raises(ConfigError, match="model"):
        load_config(cwd=tmp_path, user_config_path=user_path)


def test_max_iterations_default_when_omitted(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'model = "x"\n')

    config = load_config(cwd=tmp_path, user_config_path=user_path)
    assert config.max_iterations == Config().max_iterations


def test_max_iterations_overrides(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, "max_iterations = 100\n")

    config = load_config(cwd=tmp_path, user_config_path=user_path)
    assert config.max_iterations == 100


def test_max_iterations_wrong_type_raises(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    _write(user_path, 'max_iterations = "lots"\n')

    with pytest.raises(ConfigError, match="max_iterations"):
        load_config(cwd=tmp_path, user_config_path=user_path)


def test_save_setting_creates_file_and_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.toml"

    save_setting("model", "gpt-saved", path=path)

    assert path.is_file()
    reloaded = load_config(cwd=tmp_path / "elsewhere", user_config_path=path)
    assert reloaded.model == "gpt-saved"


def test_save_setting_updates_existing_key_and_preserves_others(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _write(path, 'model = "old"\ntemperature = 0.25\n')

    save_setting("model", "new", path=path)

    reloaded = load_config(cwd=tmp_path / "elsewhere", user_config_path=path)
    assert reloaded.model == "new"
    assert reloaded.temperature == pytest.approx(0.25)


def test_save_setting_escapes_strings(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"

    # Backslash, quote, and a newline all need escaping in a TOML basic string.
    tricky = 'has "quotes" and a\nnewline and \\ backslash'
    save_setting("system_prompt", tricky, path=path)

    reloaded = load_config(cwd=tmp_path / "elsewhere", user_config_path=path)
    assert reloaded.system_prompt == tricky
