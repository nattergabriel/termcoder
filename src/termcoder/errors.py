"""Exception hierarchy for system-level failures.

Tool failures (file not found, non-zero exit, denied permission) are not exceptions —
they flow back to the model as `ToolResult` with `is_error=True`. Exceptions are
reserved for genuine system failures that must halt the turn (provider unreachable,
auth failure, internal bug). Subclasses are added by the component that raises them.
"""


class TermcoderError(Exception):
    """Base for every exception raised by termcoder itself."""
