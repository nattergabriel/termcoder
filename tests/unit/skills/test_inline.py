"""Unit tests for inline skill activation."""

from pathlib import Path

from termcoder.skills import Skill, SkillCatalog, inject_inline_skills


def _catalog(tmp_path: Path) -> SkillCatalog:
    skill_dir = tmp_path / "python-testing"
    skill_dir.mkdir()
    location = skill_dir / "SKILL.md"
    location.write_text("", encoding="utf-8")
    return SkillCatalog(
        (
            Skill(
                name="python-testing",
                description="Write Python tests.",
                location=location,
                body="# Python Testing\nUse pytest.",
            ),
        )
    )


def test_inject_inline_skills_activates_multiple_once_in_order(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first_location = first_dir / "SKILL.md"
    second_location = second_dir / "SKILL.md"
    first_location.write_text("", encoding="utf-8")
    second_location.write_text("", encoding="utf-8")
    catalog = SkillCatalog(
        (
            Skill(
                name="first",
                description="First skill.",
                location=first_location,
                body="First body.",
            ),
            Skill(
                name="second",
                description="Second skill.",
                location=second_location,
                body="Second body.",
            ),
        )
    )

    result = inject_inline_skills("use /second then /first and /second again", catalog)

    assert result.count('<skill_content name="second">') == 1
    assert result.count('<skill_content name="first">') == 1
    assert result.index('<skill_content name="second">') < result.index(
        '<skill_content name="first">'
    )


def test_inject_inline_skills_inserts_content_before_original_prompt(tmp_path: Path) -> None:
    result = inject_inline_skills("please use /python-testing here", _catalog(tmp_path))

    assert result.startswith('<skill_content name="python-testing">')
    assert "# Python Testing" in result
    assert result.endswith("please use /python-testing here")


def test_inject_inline_skills_turns_exact_skill_token_into_minimal_prompt(tmp_path: Path) -> None:
    result = inject_inline_skills("/python-testing", _catalog(tmp_path))

    assert result.startswith('<skill_content name="python-testing">')
    assert result.endswith("Use the activated skill.")


def test_inject_inline_skills_leaves_unknown_tokens_untouched(tmp_path: Path) -> None:
    assert inject_inline_skills("please use /unknown", _catalog(tmp_path)) == "please use /unknown"
