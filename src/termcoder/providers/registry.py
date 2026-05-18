"""Provider registry — `ProviderName` → factory.

Each provider module exposes a `from_config(config) -> Provider` callable; the
registry maps the literal `ProviderName` to its factory so the composition
root picks one at runtime. Add a new backend by writing its `from_config`
and adding one entry below.
"""

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
    """Instantiate the provider selected by `config.provider`."""
    return _factories[config.provider](config)
