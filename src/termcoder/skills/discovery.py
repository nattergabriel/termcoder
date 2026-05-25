"""Agent Skills discovery."""

from dataclasses import dataclass
from pathlib import Path

_SKILL_FILENAME = "SKILL.md"


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


class SkillRegistry:
    """In-memory skill lookup by name."""

    __slots__ = ("_skills",)

    def __init__(self, skills: tuple[Skill, ...] = ()) -> None:
        self._skills = {skill.name: skill for skill in skills}

    def __bool__(self) -> bool:
        return bool(self._skills)

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._skills))

    def all(self) -> tuple[Skill, ...]:
        return tuple(self._skills[name] for name in self.names())


def discover_skills(cwd: Path | None = None, home: Path | None = None) -> SkillRegistry:
    """Discover valid SKILL.md files with deterministic collision precedence."""
    start = (cwd or Path.cwd()).resolve()
    if not start.is_dir():
        start = start.parent
    user_home = (home or Path.home()).resolve()

    skills: dict[str, Skill] = {}
    for base in (
        user_home / ".agents" / "skills",
        user_home / ".termcoder" / "skills",
        start / ".agents" / "skills",
        start / ".termcoder" / "skills",
    ):
        for skill in _discover_base(base):
            skills[skill.name] = skill
    return SkillRegistry(tuple(skills.values()))


def _discover_base(base: Path) -> tuple[Skill, ...]:
    if not base.is_dir():
        return ()
    skills: list[Skill] = []
    try:
        children = sorted(base.iterdir(), key=lambda path: path.name)
    except OSError:
        return ()
    for child in children:
        location = child / _SKILL_FILENAME
        if not child.is_dir() or not location.is_file():
            continue
        skill = _load_skill(location)
        if skill is not None:
            skills.append(skill)
    return tuple(skills)


def _load_skill(location: Path) -> Skill | None:
    try:
        content = location.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    parsed = _parse_skill_file(content)
    if parsed is None:
        return None
    metadata, body = parsed
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not name or not description:
        return None
    return Skill(
        name=name,
        description=description,
        location=location.resolve(),
        body=body,
    )


def _parse_skill_file(content: str) -> tuple[dict[str, str], str] | None:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    end_index = _frontmatter_end(lines)
    if end_index is None:
        return None

    metadata = _parse_frontmatter(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).strip()
    return metadata, body


def _frontmatter_end(lines: list[str]) -> int | None:
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return index
    return None


def _parse_frontmatter(lines: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key not in {"name", "description"}:
            continue
        metadata[key] = _strip_quotes(value.strip())
    return metadata


def _strip_quotes(value: str) -> str:
    if len(value) < 2:
        return value
    if value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
