"""Provider registry."""

from collections.abc import Callable, Mapping

from termcoder.config import Config, ProviderName
from termcoder.providers.anthropic import from_config as _build_anthropic
from termcoder.providers.openai_compatible import from_config as _build_openai
from termcoder.providers.protocol import Provider

type ProviderFactory = Callable[[Config], Provider]


_factories: Mapping[ProviderName, ProviderFactory] = {
    "openai": _build_openai,
    "anthropic": _build_anthropic,
}


def build_provider(config: Config) -> Provider:
    return _factories[config.provider](config)


def provider_names() -> tuple[ProviderName, ...]:
    return tuple(_factories)
