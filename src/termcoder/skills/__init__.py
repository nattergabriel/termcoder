"""Agent Skills discovery and activation helpers."""

from termcoder.skills.discovery import Skill, SkillRegistry, discover_skills
from termcoder.skills.inline import inject_activated_skills
from termcoder.skills.tool import ActivateSkill

__all__ = [
    "ActivateSkill",
    "Skill",
    "SkillRegistry",
    "discover_skills",
    "inject_activated_skills",
]
