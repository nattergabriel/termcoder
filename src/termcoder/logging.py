"""Logger factory — stdout belongs to user output, logs go elsewhere.

Components call `get_logger(__name__)` and log at the appropriate level. The
entry point configures handlers (level, formatter, destination). At v0.1 this
is a thin wrapper so we don't reach into `logging` directly from layer code.
"""

import logging


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
