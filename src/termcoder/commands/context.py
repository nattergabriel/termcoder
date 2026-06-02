"""Mutable command context for commands that change live app settings."""

from dataclasses import dataclass, replace
from pathlib import Path

from termcoder.agent.loop import Agent
from termcoder.config import Config, ProviderName, save_setting
from termcoder.providers.registry import build_provider


@dataclass(slots=True)
class CommandContext:
    """State shared by slash commands during a channel session."""

    agent: Agent
    config: Config
    save_path: Path

    def set_model(self, model: str) -> None:
        self.config = replace(self.config, model=model)
        self.agent.provider.model = model
        save_setting("model", model, path=self.save_path)

    def set_provider(self, provider: ProviderName) -> None:
        self.config = replace(self.config, provider=provider)
        self.agent.provider = build_provider(self.config)
        save_setting("provider", provider, path=self.save_path)

    def set_temperature(self, temperature: float) -> None:
        self.config = replace(self.config, temperature=temperature)
        self.agent.provider.temperature = temperature
        save_setting("temperature", temperature, path=self.save_path)
