"""Console-script entry point: load config, wire deps, run the selected channel."""

import asyncio
import contextlib
from pathlib import Path

from termcoder.app import build
from termcoder.channels.registry import build_channel
from termcoder.config import load_config


def main() -> None:
    cwd = Path.cwd()
    config = load_config(cwd=cwd)
    channel = build_channel(config)
    ctx = build(config, channel.confirm_tool, cwd=cwd)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(channel.run(ctx.agent, ctx.slash_commands, ctx.skills))


if __name__ == "__main__":
    main()
