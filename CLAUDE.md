# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`termcoder` — an open-source TUI coding agent in Python 3.13. Currently pre-v0.1 (scaffolding only).

**Read `PLAN.md` first.** It is the working spec: goal, six-layer architecture, MVP scope, testing strategy, error-handling philosophy, and configuration model. The plan supersedes this file when they conflict.

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

Detailed in `PLAN.md`. Briefly: six independently-testable layers — `providers/` (LLM abstraction), `tools/` (pluggable read/write/bash), `agent/` (pure orchestration loop), `context/` (history + system-prompt assembly), `permissions/` (gates dangerous tools), `tui/` (Textual view).

The provider seam **must** support a hand-written `FakeProvider` for tests. Design the interface around that constraint, not around the OpenAI SDK's shape — most tests will run against the fake with no network and no API key.

## Code style and conventions

- **mypy is strict.** Every function (including tests) needs full type annotations. Don't add `# type: ignore` without a comment explaining why.
- **No filesystem mocks in tool tests.** Use pytest's `tmp_path` fixture and exercise real I/O.
- **Tool errors are LLM input, not exceptions.** When a tool fails (file not found, command exits non-zero), return the error text as the tool result so the agent can react. Only let exceptions escape for genuine system failures (provider unreachable, internal bugs).
- **Comments only when the *why* is non-obvious.** Don't paraphrase what the code already says.
- **Conventional Commits** — `feat:`, `chore:`, `fix:`, `docs:`, `test:`, `refactor:`. Match the style of existing commits.

## Design principles

- **YAGNI is enforced.** Don't pre-build for the post-v0.1 roadmap. Three similar lines is better than a premature abstraction. A registry for three tools is fine; a plugin system for three tools is overengineered.
- **Isolate I/O at the edges.** `agent/`, `context/`, and `permissions/` are pure orchestration — no `print`, no file I/O, no network. Side effects live in `tools/`, `providers/`, and `tui/`. This is what makes the agent loop testable with a `FakeProvider`.
- **`typing.Protocol` over base classes.** Layer seams (provider, tool, permission policy) are structural. Avoid ABCs and deep inheritance.
- **Domain types over primitives.** Give meaningful concepts their own type (`ToolName`, `PermissionDecision`, `Turn`, …). Avoid `dict[str, Any]` at module boundaries — mypy can't help you there.
- **Flat over nested.** Early returns over `else` ladders; short functions over 50-line bodies. If a function needs scrolling to read, it's doing too much.

## Modularity

Swap a provider, tool, permission policy, or TUI without touching the agent core. The mechanisms:

- **Protocols at every layer seam.** Provider, Tool, Permission policy are all `typing.Protocol`s. Adding an implementation = writing a class that satisfies the Protocol — no inheritance, no base-class registration.
- **Dependency injection at the composition root.** `cli.py` wires the system; the agent receives `provider`, `tools`, `permissions` as constructor args. Nothing inside `agent.py` imports a concrete provider or tool.
- **Stable internal types as the lingua franca.** `Message`, `Turn`, `ToolCall`, `ToolResult` live in `types.py`. Each provider adapts to/from those types at its boundary; the core never sees OpenAI/Anthropic-shaped data.
- **Registry + name lookup for tools and providers.** Registration is one line per new component; selection is config-driven, not import-driven.
- **No module-level singletons or globals.** State that outlives a single call belongs in an explicit object threaded through constructors.

## Project layout

`src/termcoder/<layer>/...` with one `base.py` per layer for its `Protocol`(s) and concrete implementations alongside. `tests/` mirrors the source tree 1:1, with shared fakes in `tests/fakes/` and full-loop tests in `tests/integration/`. Entry point: `termcoder.cli:main` exposed via `[project.scripts]`. No `utils/` folder. Folders appear as code lands in them — don't pre-create empty packages.

## What not to add

This is a deliberately small foundation. Until v0.1 ships, do not introduce:

- Backwards-compatibility shims, feature flags, or stub interfaces for anything `PLAN.md` defers to post-v0.1.
- Sandboxing, telemetry, session persistence, sub-agents, or MCP integration.
- A docs site (`mkdocs` / `sphinx`). README + PLAN suffice.
- Long-form prose in `PLAN.md` for things already enforced by tooling (CI config, hook config, license) — keep the plan lean.
