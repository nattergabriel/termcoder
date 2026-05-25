"""Skill discovery and activation content."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Skill:
    """A discovered Agent Skill."""

    name: str
    description: str
    location: Path
    body: str

    @property
    def directory(self) -> Path:
        return self.location.parent


@dataclass(frozen=True, slots=True)
class SkillCatalog:
    """Lookup and formatting for discovered skills."""

    skills: tuple[Skill, ...]

    def __post_init__(self) -> None:
        names = {skill.name for skill in self.skills}
        if len(names) != len(self.skills):
            raise ValueError("duplicate skill names")

    def names(self) -> tuple[str, ...]:
        return tuple(skill.name for skill in self.skills)

    def get(self, name: str) -> Skill | None:
        for skill in self.skills:
            if skill.name == name:
                return skill
        return None

    def activation_content(self, name: str) -> str | None:
        skill = self.get(name)
        if skill is None:
            return None
        return format_activation(skill)

    def compact_catalog(self) -> str:
        lines = ["Available skills:"]
        for skill in self.skills:
            lines.append(f"- {skill.name}: {skill.description}")
        return "\n".join(lines)


def discover_skills(cwd: Path | None = None) -> SkillCatalog:
    """Discover skills using deterministic low-to-high precedence."""
    root = (cwd or Path.cwd()).resolve()
    by_name: dict[str, Skill] = {}
    for skills_dir in _skills_dirs(root):
        for skill_path in _skill_files(skills_dir):
            skill = _parse_skill(skill_path)
            if skill is not None:
                by_name[skill.name] = skill
    return SkillCatalog(tuple(sorted(by_name.values(), key=lambda skill: skill.name)))


def format_activation(skill: Skill) -> str:
    resources, truncated = _resource_listing(skill.directory)
    lines = [
        f'<skill_content name="{skill.name}">',
        skill.body,
        "",
        f"Skill directory: {skill.directory}",
        "Relative paths in this skill are relative to the skill directory.",
        "<skill_resources>",
    ]
    lines.extend(f"  <file>{path}</file>" for path in resources)
    if truncated:
        lines.append("  <truncated>true</truncated>")
    lines.extend(["</skill_resources>", "</skill_content>"])
    return "\n".join(lines)


def _skills_dirs(cwd: Path) -> tuple[Path, ...]:
    home = Path.home()
    return (
        home / ".agents" / "skills",
        home / ".termcoder" / "skills",
        cwd / ".agents" / "skills",
        cwd / ".termcoder" / "skills",
    )


def _skill_files(skills_dir: Path) -> tuple[Path, ...]:
    try:
        children = sorted(skills_dir.iterdir(), key=lambda path: path.name)
    except OSError:
        return ()
    return tuple(child / "SKILL.md" for child in children if (child / "SKILL.md").is_file())


def _parse_skill(path: Path) -> Skill | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    frontmatter, body = _split_frontmatter(raw)
    if frontmatter is None:
        return None
    fields = _parse_frontmatter(frontmatter)
    name = fields.get("name", "").strip()
    description = fields.get("description", "").strip()
    if not name or not description:
        return None
    return Skill(
        name=name,
        description=description,
        location=path.resolve(),
        body=body.strip(),
    )


def _split_frontmatter(raw: str) -> tuple[str | None, str]:
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, ""
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    return None, ""


def _parse_frontmatter(raw: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = stripped.partition(":")
        if not sep:
            continue
        fields[key.strip()] = _strip_quotes(value.strip())
    return fields


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _resource_listing(directory: Path, *, limit: int = 50) -> tuple[tuple[str, ...], bool]:
    resources: list[str] = []
    truncated = False
    for root, dirs, files in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if d not in {".git", "__pycache__", "node_modules"})
        for filename in sorted(files):
            path = Path(root) / filename
            if path.name == "SKILL.md":
                continue
            if len(resources) >= limit:
                return tuple(resources), True
            resources.append(path.relative_to(directory).as_posix())
    return tuple(resources), truncated
