"""Unit tests for inline skill activation."""

from pathlib import Path

from termcoder.skills import Skill, SkillRegistry, inject_activated_skills


def _skill(name: str) -> Skill:
    return Skill(
        name=name,
        description=f"{name} description.",
        location=Path("/") / name / "SKILL.md",
        body=f"{name} body",
    )


def test_injects_known_skill_tokens_once_in_first_mention_order() -> None:
    skills = SkillRegistry((_skill("python-testing"), _skill("docs")))

    result = inject_activated_skills(
        "please use /python-testing, then /docs and /python-testing again",
        skills,
    )

    assert result.index('name="python-testing"') < result.index('name="docs"')
    assert result.count('name="python-testing"') == 1
    assert result.endswith("please use /python-testing, then /docs and /python-testing again")


def test_exact_skill_token_uses_minimal_prompt() -> None:
    result = inject_activated_skills("/python-testing", SkillRegistry((_skill("python-testing"),)))

    assert result.endswith("Use the activated skill.")
    assert "/python-testing" not in result.rsplit("\n\n", maxsplit=1)[-1]


def test_unknown_tokens_are_left_untouched() -> None:
    prompt = "please use /missing"

    assert inject_activated_skills(prompt, SkillRegistry((_skill("known"),))) == prompt
