"""Unit tests for skill discovery."""

from pathlib import Path

from termcoder.skills import discover_skills


def _write_skill(directory: Path, *, name: str, description: str, body: str = "Body.") -> None:
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_discovers_skills_with_expected_collision_precedence(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    _write_skill(
        home / ".agents" / "skills" / "shared",
        name="shared",
        description="user cross-client",
    )
    _write_skill(
        home / ".termcoder" / "skills" / "shared",
        name="shared",
        description="user native",
    )
    _write_skill(
        project / ".agents" / "skills" / "shared",
        name="shared",
        description="project cross-client",
    )
    _write_skill(
        project / ".termcoder" / "skills" / "shared",
        name="shared",
        description="project native",
        body="# Project skill",
    )

    skills = discover_skills(cwd=project, home=home)
    skill = skills.get("shared")

    assert skill is not None
    assert skill.description == "project native"
    assert skill.body == "# Project skill"
    assert skill.location == (project / ".termcoder" / "skills" / "shared" / "SKILL.md")
    assert skill.location.is_absolute()


def test_skips_malformed_or_incomplete_skills(tmp_path: Path) -> None:
    project = tmp_path / "project"
    malformed = project / ".termcoder" / "skills" / "malformed"
    incomplete = project / ".termcoder" / "skills" / "incomplete"
    valid = project / ".termcoder" / "skills" / "valid"
    malformed.mkdir(parents=True)
    incomplete.mkdir(parents=True)
    (malformed / "SKILL.md").write_text("name: malformed\n", encoding="utf-8")
    (incomplete / "SKILL.md").write_text("---\nname: incomplete\n---\nBody\n", encoding="utf-8")
    _write_skill(valid, name="valid", description="Works.")

    skills = discover_skills(cwd=project, home=tmp_path / "home")

    assert skills.names() == ("valid",)
