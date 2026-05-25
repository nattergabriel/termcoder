"""Agent Skills support."""

from termcoder.skills.catalog import Skill, SkillCatalog, discover_skills
from termcoder.skills.inline import inject_inline_skills
from termcoder.skills.tool import ActivateSkill

__all__ = ["ActivateSkill", "Skill", "SkillCatalog", "discover_skills", "inject_inline_skills"]
