"""Inline slash-token skill activation."""

import re

from termcoder.skills.catalog import SkillCatalog

_SKILL_TOKEN = re.compile(r"(?<!\w)/([A-Za-z0-9_.-]+)")


def inject_inline_skills(user_input: str, catalog: SkillCatalog) -> str:
    """Inject activated skill content for known `/skill-name` tokens."""
    names = set(catalog.names())
    if not names:
        return user_input

    activated: list[str] = []
    seen: set[str] = set()
    for match in _SKILL_TOKEN.finditer(user_input):
        name = match.group(1)
        if name not in names or name in seen:
            continue
        seen.add(name)
        activated.append(name)

    if not activated:
        return user_input

    blocks = [content for name in activated if (content := catalog.activation_content(name))]
    if not blocks:
        return user_input

    stripped = user_input.strip()
    if len(activated) == 1 and stripped == f"/{activated[0]}":
        prompt = "Use the activated skill."
    else:
        prompt = user_input
    return "\n\n".join([*blocks, prompt])
