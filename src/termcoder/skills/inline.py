"""Inline slash activation for discovered skills."""

import re

from termcoder.skills.discovery import Skill, SkillRegistry
from termcoder.skills.tool import render_skill_content

_SKILL_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_/-])/(?P<name>[A-Za-z0-9][A-Za-z0-9_-]*)(?![A-Za-z0-9_/-])"
)
_EXACT_PROMPT = "Use the activated skill."


def inject_activated_skills(user_input: str, skills: SkillRegistry) -> str:
    """Inject activated skill content before the prompt when known tokens are present."""
    activated = _mentioned_skills(user_input, skills)
    if not activated:
        return user_input

    stripped = user_input.strip()
    prompt = (
        _EXACT_PROMPT if len(activated) == 1 and stripped == f"/{activated[0].name}" else user_input
    )
    blocks = [render_skill_content(skill) for skill in activated]
    return "\n\n".join([*blocks, prompt])


def _mentioned_skills(user_input: str, skills: SkillRegistry) -> tuple[Skill, ...]:
    activated: list[Skill] = []
    seen: set[str] = set()
    for match in _SKILL_TOKEN.finditer(user_input):
        name = match.group("name")
        if name in seen:
            continue
        skill = skills.get(name)
        if skill is None:
            continue
        activated.append(skill)
        seen.add(name)
    return tuple(activated)
