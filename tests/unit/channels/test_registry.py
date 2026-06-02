"""Tests for the channel registry."""

from termcoder.channels.registry import build_channel, channel_names
from termcoder.channels.terminal import TerminalChannel
from termcoder.config import Config


def test_builds_terminal_channel_from_config() -> None:
    channel = build_channel(Config(channel="terminal"))

    assert isinstance(channel, TerminalChannel)


def test_channel_names_returns_registered_channels() -> None:
    assert channel_names() == ("terminal",)
