"""System-prompt assembly."""

DEFAULT_SYSTEM_PROMPT = (
    "You are termcoder, a terminal-based coding assistant. "
    "Be concise, prefer small focused actions, and ask the user before destructive operations."
)


def assemble_system_prompt(custom_instructions: str | None = None) -> str:
    """Return the system prompt, optionally appending user-supplied instructions."""
    if not custom_instructions:
        return DEFAULT_SYSTEM_PROMPT
    return f"{DEFAULT_SYSTEM_PROMPT}\n\n{custom_instructions}"
