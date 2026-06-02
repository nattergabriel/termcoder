"""Channel registry."""

from collections.abc import Callable, Mapping

from termcoder.channels.protocol import Channel
from termcoder.channels.telegram import TelegramChannel
from termcoder.channels.terminal import TerminalChannel
from termcoder.config import ChannelName, Config

type ChannelFactory = Callable[[Config], Channel]


_factories: Mapping[ChannelName, ChannelFactory] = {
    "terminal": lambda _config: TerminalChannel(),
    "telegram": lambda config: TelegramChannel(allowed_chat_id=config.telegram_chat_id),
}


def build_channel(config: Config) -> Channel:
    return _factories[config.channel](config)


def channel_names() -> tuple[ChannelName, ...]:
    return tuple(_factories)
