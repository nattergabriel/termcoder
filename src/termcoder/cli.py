"""Console-script entry point: load config, wire deps, run the REPL."""

import asyncio
import contextlib
from pathlib import Path

from termcoder.app import build
from termcoder.config import load_config
from termcoder.ui.repl import Repl


def main() -> None:
    cwd = Path.cwd()
    config = load_config(cwd=cwd)
    repl = Repl()
    ctx = build(config, repl.confirm_tool, cwd=cwd)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(repl.run(ctx.agent, ctx.slash_commands, ctx.skills))


if __name__ == "__main__":
    main()
