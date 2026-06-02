"""Tests for the channel registry."""

import pytest

from termcoder.channels.registry import build_channel, channel_names
from termcoder.channels.telegram import TelegramChannel
from termcoder.channels.terminal import TerminalChannel
from termcoder.config import Config


def test_builds_terminal_channel_from_config() -> None:
    channel = build_channel(Config(channel="terminal"))

    assert isinstance(channel, TerminalChannel)


def test_builds_telegram_channel_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")

    channel = build_channel(Config(channel="telegram"))

    assert isinstance(channel, TelegramChannel)


def test_channel_names_returns_registered_channels() -> None:
    assert channel_names() == ("terminal", "telegram")
