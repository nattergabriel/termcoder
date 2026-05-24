"""Unit tests for AGENTS.md instruction loading."""

from pathlib import Path

from termcoder.instructions import load_agent_instruction_files


def test_loads_agents_files_from_parent_hierarchy_to_cwd(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    nested = root / "packages" / "app"
    nested.mkdir(parents=True)
    (tmp_path / "AGENTS.md").write_text("parent\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("root\n", encoding="utf-8")
    (nested / "AGENTS.md").write_text("nested\n", encoding="utf-8")

    files = load_agent_instruction_files(nested)

    assert [file.path for file in files] == [
        tmp_path / "AGENTS.md",
        root / "AGENTS.md",
        nested / "AGENTS.md",
    ]
    assert [file.content for file in files] == ["parent\n", "root\n", "nested\n"]


def test_project_root_markers_do_not_stop_parent_hierarchy_loading(tmp_path: Path) -> None:
    outer = tmp_path / "AGENTS.md"
    root = tmp_path / "repo"
    nested = root / "pkg"
    nested.mkdir(parents=True)
    outer.write_text("outer\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / "AGENTS.md").write_text("root\n", encoding="utf-8")

    files = load_agent_instruction_files(nested)

    assert [file.path for file in files] == [outer, root / "AGENTS.md"]


def test_uses_file_parent_when_cwd_is_file(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    target = root / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('hi')\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("root\n", encoding="utf-8")

    files = load_agent_instruction_files(target)

    assert [file.path for file in files] == [root / "AGENTS.md"]


def test_ignores_empty_agents_files(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("\n\n", encoding="utf-8")

    assert load_agent_instruction_files(tmp_path) == ()


def test_ignores_agents_files_in_subdirectories(tmp_path: Path) -> None:
    child = tmp_path / "child"
    child.mkdir()
    (child / "AGENTS.md").write_text("child\n", encoding="utf-8")

    assert load_agent_instruction_files(tmp_path) == ()
