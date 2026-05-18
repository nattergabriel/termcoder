# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`termcoder` — an open-source TUI coding agent in Python 3.13.

## Commands

All commands assume `uv` is installed. One-time setup after cloning: `uv sync && uv run pre-commit install`.

- `uv sync` — install dependencies (also run after pulling changes to `pyproject.toml` or `uv.lock`).
- `uv run termcoder` — launch the TUI (once the entry point exists).
- `uv run pytest` — run the full test suite.
- `uv run pytest tests/test_smoke.py::test_smoke` — run a single test.
- `uv run pytest -k <pattern>` — run tests matching `<pattern>`.
- `uv run ruff check` / `uv run ruff format` — lint and format.
- `uv run mypy .` — type-check (strict mode).
- `uv run pre-commit run --all-files` — run every pre-commit hook against the whole tree.
- `uv run pre-commit autoupdate` — bump pinned hook versions.

CI (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check`, `mypy .`, and `pytest`. Run them locally before opening a PR.

## Architecture

> **Source of truth for structure.** This section and **Project layout** below are the only place that describes the codebase's organization. Update them whenever you add, rename, move, or remove a file or folder — and only here.

Briefly: three layer packages plus cross-cutting root modules.

- **Layer packages:** `providers/` (LLM abstraction), `tools/` (one file per tool behind a Protocol + registry), `agent/` (orchestration loop, event-log state, prompt assembly).
- **Cross-cutting at the root:** `types.py` (shared types), `events.py` (typed `AgentEvent` stream), `composition.py` (composition root: builds the `AppContext`), `cli.py` (entry point), `config.py`, `permissions.py` (policy functions; `ask_each` at v0.1, more modes join the same file as the roadmap lands), `slash_commands.py` (registry + dispatch for `/`-prefixed REPL directives), `errors.py`, `logging.py`, `repl.py` (rich-rendered output + prompt_toolkit input — the only file that imports either).

Two things the loop produces that everything else consumes: `AgentEvent`s (the streaming output of `agent/loop.py`, consumed by the REPL as an async iterator) and shared domain types (`Message`, `Turn`, `ToolCall`, `ToolResult`). Keep both stable — they are the contract.

The provider seam **must** support a hand-written `FakeProvider` for tests. Design the interface around that constraint, not around any specific vendor's wire format or SDK shape — most tests run against the fake with no network and no API key.

Configuration loads from env (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `ANTHROPIC_API_KEY`) for secrets and from TOML for settings, with precedence `.termcoder.toml` (project) > `~/.config/termcoder/config.toml` (user) > built-in defaults.

## Code style and conventions

- **mypy is strict.** Every function (including tests) needs full type annotations. Don't add `# type: ignore` without a comment explaining why.
- **No filesystem mocks in tool tests.** Use pytest's `tmp_path` fixture and exercise real I/O.
- **Tool errors are LLM input, not exceptions.** When a tool fails (file not found, command exits non-zero), return the error text as the tool result so the agent can react. Only let exceptions escape for genuine system failures (provider unreachable, internal bugs) — those halt the turn and surface to the user.
- **Comments only when the *why* is non-obvious.** Don't paraphrase what the code already says.
- **Conventional Commits** — `feat:`, `chore:`, `fix:`, `docs:`, `test:`, `refactor:`. Match the style of existing commits.

## Git workflow

One PR per logical change (feature, bug fix, refactor, docs update). The user reviews changes in VSCode's source-control view; the AI agent commits and pushes on approval, and opens the PR on a separate signal when the work is ready to share. Merging stays with the user.

- **Branch per change.** `git switch -c <short-slug>` (e.g. `add-edit-tool`, `fix-bash-stderr`) off the latest `main`. Never work on `main` directly. Pulling on `main` is fine; committing on it is not.
- **Don't auto-commit.** Stop after writing changes and let the user review. When they say to commit ("commit," "ship it," "looks good"), run `git commit` (Conventional Commits per § Code style) and `git push -u origin <branch>`. Push every commit — it keeps the remote branch current and is harmless on a feature branch. Natural milestones (e.g. `feat:` for code + `test:` for tests) get their own commit; a single PR will often contain several.
- **Don't auto-PR.** A branch can hold multiple commits before its PR opens. Wait for an explicit signal ("open PR," "PR it"), then run `gh pr create --title "..." --body "..."` with a real body covering the *whole branch's* work — what changed and why, test plan if relevant. Once the PR is open, additional commits on the branch update it automatically; don't open another.
- **Stop after the PR is open.** Don't run `gh pr merge` — the user merges on GitHub after reviewing the PR and CI.
- **No history rewrites.** No `git commit --amend`, no `git rebase`, no `git reset` past committed work. Each commit lands on `main` (rebase-merge), so write meaningful commit messages and treat review fixes as new commits, not amendments.

## Design principles

- **Isolate I/O at the edges.** `agent/`, `permissions.py`, `types.py`, `events.py`, `errors.py` are pure — no `print`, no file I/O, no network. Side effects live in `tools/`, `providers/`, `repl.py`, `config.py`, `logging.py`. This is what makes the agent loop testable with a `FakeProvider`.
- **`typing.Protocol` over base classes.** Layer seams (provider, tool, permission policy) are structural. Avoid ABCs and deep inheritance.
- **Domain types over primitives.** Give meaningful concepts their own type (`ToolName`, `PermissionDecision`, `Turn`, …). Avoid `dict[str, Any]` at module boundaries — mypy can't help you there.
- **Flat over nested.** Early returns over `else` ladders; short functions over 50-line bodies. If a function needs scrolling to read, it's doing too much.

## Modularity

Swap a provider, tool, permission policy, or TUI without touching the agent core. The mechanisms:

- **Protocols where there's swappability or a test fake.** `Provider` and `Tool` meet that bar — each has multiple implementations and a dedicated fake. Single-impl concepts (`AppContext`, `Config`, `State`, permission functions) use plain classes / plain functions; promote to Protocol when the second implementation actually appears.
- **Dependency injection at the composition root.** `composition.py` builds the `AppContext`; `cli.py` invokes it and hands it to `repl.py`. The agent receives `provider`, `tools`, and a permission-check callable as constructor args. Nothing inside `agent/` or `permissions.py` imports a concrete provider, tool, or UI — the user-prompt is passed in as a callable at composition time.
- **Stable internal types as the lingua franca.** `Message`, `Turn`, `ToolCall`, `ToolResult` live in `types.py`; `AgentEvent` in `events.py`. Each provider adapts to/from those types at its boundary; the core never sees OpenAI/Anthropic-shaped data.
- **Registry + name lookup for tools** (and for providers once a second one lands). Registration is one line per new entry; selection is config-driven, not import-driven.
- **No module-level singletons or globals.** State that outlives a single call belongs in an explicit object threaded through constructors.

## Project layout

```
src/termcoder/
├── __init__.py
├── __main__.py             # `python -m termcoder` shortcut
├── cli.py                  # entry point: calls composition, runs the session loop
├── composition.py          # builds the AppContext: wires all deps
├── config.py               # loading + precedence (project > user > defaults)
├── types.py                # Message, Turn, ToolCall, ToolResult, Role
├── events.py               # AgentEvent union: TextDelta, ToolCallStart, ToolCallResult, ...
├── errors.py               # TermcoderError hierarchy
├── logging.py              # get_logger wrapper (REPL owns stdout)
├── slash_commands.py       # `/model …` etc.: registry + dispatch; handlers bound at composition
├── agent/
│   ├── __init__.py
│   ├── loop.py             # async generator: yields AgentEvent
│   ├── state.py            # event log + derived views (messages list, etc.)
│   └── prompt.py           # system-prompt assembly (pure function)
├── providers/
│   ├── __init__.py
│   ├── protocol.py         # Provider Protocol
│   ├── openai_compatible.py
│   └── anthropic.py        # one file per backend
├── tools/
│   ├── __init__.py
│   ├── protocol.py         # Tool Protocol
│   ├── registry.py
│   ├── read.py             # one file per tool
│   ├── write.py
│   └── bash.py
├── permissions.py          # ask_each at v0.1; allow_list / auto_approve / deny_list join here
└── repl.py                 # rich for streamed output, prompt_toolkit for input + inline [y/N]; only file that imports either

tests/
├── __init__.py
├── conftest.py
├── fakes/
│   ├── __init__.py
│   ├── fake_provider.py    # scripted AgentEvent streams
│   ├── fake_tool.py
│   └── fake_permission.py  # auto-allow / auto-deny / scripted
├── fixtures/
│   └── transcripts/        # hand-crafted JSON fixtures for real-provider smoke tests
├── unit/                   # mirrors src/termcoder/ where useful, not religiously
│   ├── agent/
│   ├── providers/
│   ├── tools/
│   └── test_permissions.py
└── integration/
    ├── test_full_loop.py   # FakeProvider + real tools in tmp_path
    └── test_repl_smoke.py  # FakeProvider + scripted prompt session
```

**Folder rule:** a folder is justified when ≥2 files exist *or will soon exist* that each need real space — distinct imports, distinct test fixtures, or substantive code (typically >50 lines each). Build for known growth, not for speculative plurality.

## What not to add

This is a deliberately small foundation. Do not introduce:

- Backwards-compatibility shims, feature flags, or stub interfaces for speculative future work.
- Sandboxing, telemetry, session persistence, sub-agents, or MCP integration.
- A docs site (`mkdocs` / `sphinx`). README suffices.
