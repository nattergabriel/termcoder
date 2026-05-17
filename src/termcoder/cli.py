"""Console-script entry point: load config, wire deps, run the REPL."""

import asyncio
import contextlib

from termcoder.composition import build
from termcoder.config import load_config
from termcoder.repl import Repl


def main() -> None:
    config = load_config()
    repl = Repl()
    ctx = build(config, repl.confirm_tool)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(repl.run(ctx.agent))


if __name__ == "__main__":
    main()
