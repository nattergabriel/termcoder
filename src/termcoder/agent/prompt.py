"""System-prompt assembly — pure, side-effect free.

Kept deliberately small at v0.1: a single base instruction with an optional
user-supplied addendum. The tool catalog is advertised separately via the
provider, so we don't repeat it here. Grow the inputs (cwd, project notes,
etc.) only when a concrete need lands.
"""

DEFAULT_SYSTEM_PROMPT = (
    "You are termcoder, a terminal-based coding assistant. "
    "Be concise, prefer small focused actions, and ask the user before destructive operations."
)


def assemble_system_prompt(custom_instructions: str | None = None) -> str:
    """Return the system prompt, optionally appending user-supplied instructions."""
    if not custom_instructions:
        return DEFAULT_SYSTEM_PROMPT
    return f"{DEFAULT_SYSTEM_PROMPT}\n\n{custom_instructions}"
