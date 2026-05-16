# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`termcoder` — an open-source TUI coding agent in Python 3.13. Currently pre-v0.1 (scaffolding only).

**Read `PLAN.md` first.** It is the working spec: goal, layered architecture, MVP scope, testing strategy, error-handling philosophy, and configuration model. The plan supersedes this file when they conflict.

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

> **Source of truth for structure.** This section and **Project layout** below are the only place that describes the codebase's organization. Update them whenever you add, rename, move, or remove a file or folder — and only here. `PLAN.md` deliberately defers to this file so the structure lives in one place.

Briefly: four layer packages plus cross-cutting root modules.

- **Layer packages:** `providers/` (LLM abstraction), `tools/` (one file per tool behind a Protocol + registry), `agent/` (orchestration loop, event-log state, prompt assembly), `tui/` (Textual app + widgets).
- **Cross-cutting at the root:** `types.py` (shared types), `events.py` (typed `AgentEvent` stream), `composition.py` (composition root: builds the `AppContext`), `cli.py` (entry point), `config.py`, `permissions.py` (policy functions; `ask_each` at v0.1, more modes join the same file as the roadmap lands), `errors.py`, `logging.py`.

Two things the loop produces that everything else consumes: `AgentEvent`s (the streaming output of `agent/loop.py`, consumed by the TUI as an async iterator) and shared domain types (`Message`, `Turn`, `ToolCall`, `ToolResult`). Keep both stable — they are the contract.

The provider seam **must** support a hand-written `FakeProvider` for tests. Design the interface around that constraint, not around any specific vendor's wire format or SDK shape — most tests run against the fake with no network and no API key.

## Code style and conventions

- **mypy is strict.** Every function (including tests) needs full type annotations. Don't add `# type: ignore` without a comment explaining why.
- **No filesystem mocks in tool tests.** Use pytest's `tmp_path` fixture and exercise real I/O.
- **Tool errors are LLM input, not exceptions.** When a tool fails (file not found, command exits non-zero), return the error text as the tool result so the agent can react. Only let exceptions escape for genuine system failures (provider unreachable, internal bugs).
- **Comments only when the *why* is non-obvious.** Don't paraphrase what the code already says.
- **Conventional Commits** — `feat:`, `chore:`, `fix:`, `docs:`, `test:`, `refactor:`. Match the style of existing commits.

## Design principles

- **YAGNI is enforced.** Don't pre-build for the post-v0.1 roadmap. Three similar lines is better than a premature abstraction. A registry for three tools is fine; a plugin system for three tools is overengineered.
- **Isolate I/O at the edges.** `agent/`, `permissions.py`, `types.py`, `events.py`, `errors.py` are pure — no `print`, no file I/O, no network. Side effects live in `tools/`, `providers/`, `tui/`, `config.py`, `logging.py`. This is what makes the agent loop testable with a `FakeProvider`.
- **`typing.Protocol` over base classes.** Layer seams (provider, tool, permission policy) are structural. Avoid ABCs and deep inheritance.
- **Domain types over primitives.** Give meaningful concepts their own type (`ToolName`, `PermissionDecision`, `Turn`, …). Avoid `dict[str, Any]` at module boundaries — mypy can't help you there.
- **Flat over nested.** Early returns over `else` ladders; short functions over 50-line bodies. If a function needs scrolling to read, it's doing too much.

## Modularity

Swap a provider, tool, permission policy, or TUI without touching the agent core. The mechanisms:

- **Protocols where there's swappability or a test fake.** `Provider` and `Tool` meet that bar — each has multiple implementations and a dedicated fake. Single-impl concepts (`AppContext`, `Config`, `State`, permission functions) use plain classes / plain functions; promote to Protocol when the second implementation actually appears.
- **Dependency injection at the composition root.** `composition.py` builds the `AppContext`; `cli.py` invokes it. The agent receives `provider`, `tools`, and a permission-check callable as constructor args. Nothing inside `agent/` or `permissions.py` imports a concrete provider, tool, or UI — the user-prompt is passed in as a callable at composition time.
- **Stable internal types as the lingua franca.** `Message`, `Turn`, `ToolCall`, `ToolResult` live in `types.py`; `AgentEvent` in `events.py`. Each provider adapts to/from those types at its boundary; the core never sees OpenAI/Anthropic-shaped data.
- **Registry + name lookup for tools** (and for providers once a second one lands). Registration is one line per new entry; selection is config-driven, not import-driven.
- **No module-level singletons or globals.** State that outlives a single call belongs in an explicit object threaded through constructors.

## Project layout

```
src/termcoder/
├── __init__.py
├── __main__.py             # `python -m termcoder` shortcut
├── py.typed                # mypy strict marker for downstream consumers
├── cli.py                  # argv parsing → calls composition → runs
├── composition.py          # builds the AppContext: wires all deps
├── config.py               # loading + precedence (CLI > project > user > defaults)
├── types.py                # Message, Turn, ToolCall, ToolResult, Role
├── events.py               # AgentEvent union: TextDelta, ToolCallStart, ToolCallResult, ...
├── errors.py               # TermcoderError hierarchy
├── logging.py              # get_logger wrapper (TUI owns stdout)
├── agent/
│   ├── __init__.py
│   ├── loop.py             # async generator: yields AgentEvent
│   ├── state.py            # event log + derived views (messages list, etc.)
│   └── prompt.py           # system-prompt assembly (pure function)
├── providers/
│   ├── __init__.py
│   ├── protocol.py         # Provider Protocol
│   └── openai_compatible.py  # v0.1 has one provider; add registry.py when a second lands
├── tools/
│   ├── __init__.py
│   ├── protocol.py         # Tool Protocol
│   ├── registry.py
│   ├── read.py             # one file per tool
│   ├── write.py
│   └── bash.py
├── permissions.py          # ask_each at v0.1; allow_list / auto_approve / deny_list join here
└── tui/
    ├── __init__.py
    ├── app.py              # Textual App; only file that imports textual
    └── widgets/
        ├── __init__.py
        ├── transcript.py
        ├── input.py
        └── permission_modal.py

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
    └── test_tui_smoke.py   # Textual Pilot
```

**Folder rule:** a folder is justified when ≥2 files exist *or will soon exist* that each need real space — distinct imports, distinct test fixtures, or substantive code (typically >50 lines each). Build for known growth, not for speculative plurality. `agent/`, `providers/`, `tools/`, `tui/widgets/` qualify (each future addition is substantial). `permissions.py` doesn't (every mode is a ~10-line function of the same shape). Promote a file to a folder when one entry crosses ~250 lines or holds genuinely unrelated concerns. No `utils/` folder, ever.

## What not to add

This is a deliberately small foundation. Until v0.1 ships, do not introduce:

- Backwards-compatibility shims, feature flags, or stub interfaces for anything `PLAN.md` defers to post-v0.1.
- Sandboxing, telemetry, session persistence, sub-agents, or MCP integration.
- A docs site (`mkdocs` / `sphinx`). README + PLAN suffice.
- Long-form prose in `PLAN.md` for things already enforced by tooling (CI config, hook config, license) — keep the plan lean.
