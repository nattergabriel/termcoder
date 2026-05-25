"""Unit tests for skill discovery."""

from pathlib import Path

import pytest

from termcoder.skills import discover_skills


def _write_skill(path: Path, *, name: str, description: str, body: str) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )


def test_discover_skills_loads_valid_skill_metadata_and_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    monkeypatch.setenv("HOME", str(home))
    _write_skill(
        project / ".termcoder" / "skills" / "python-testing" / "SKILL.md",
        name="python-testing",
        description="Write Python tests.",
        body="# Python Testing\nUse pytest.",
    )

    catalog = discover_skills(project)
    skill = catalog.get("python-testing")

    assert skill is not None
    assert skill.description == "Write Python tests."
    assert skill.location.is_absolute()
    assert skill.body == "# Python Testing\nUse pytest."


def test_discover_skills_applies_documented_collision_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    monkeypatch.setenv("HOME", str(home))
    locations = (
        home / ".agents" / "skills" / "same" / "SKILL.md",
        home / ".termcoder" / "skills" / "same" / "SKILL.md",
        project / ".agents" / "skills" / "same" / "SKILL.md",
        project / ".termcoder" / "skills" / "same" / "SKILL.md",
    )
    for index, location in enumerate(locations):
        _write_skill(
            location,
            name="same",
            description=f"Description {index}.",
            body=f"body {index}",
        )

    skill = discover_skills(project).get("same")

    assert skill is not None
    assert skill.body == "body 3"


def test_discover_skills_skips_malformed_and_incomplete_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    monkeypatch.setenv("HOME", str(home))
    malformed = project / ".termcoder" / "skills" / "bad" / "SKILL.md"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("name: bad\n", encoding="utf-8")
    missing_description = project / ".termcoder" / "skills" / "missing" / "SKILL.md"
    missing_description.parent.mkdir(parents=True)
    missing_description.write_text("---\nname: missing\n---\nbody\n", encoding="utf-8")

    catalog = discover_skills(project)

    assert catalog.names() == ()
