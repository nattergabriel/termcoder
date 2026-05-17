# termcoder — Plan

A working plan. Iterate freely. Things land in code only after they survive a few passes here.

## Goal

An open-source Python TUI coding agent. Foundation-first: well-structured, extensible, documented. Not chasing feature parity with Claude Code / Aider / Cursor — aiming for a clean base that's a pleasure to read, extend, and benchmark against.

## Stack

- **Python 3.13**
- **Textual** — TUI framework
- **OpenAI Python SDK** for the Chat Completions streaming wire; any OpenAI-compatible endpoint works (OpenAI, OpenRouter, Groq, DeepSeek, Together, local llama.cpp/Ollama, …) via `base_url` override. SDK types stay inside `providers/openai_compatible.py` — the agent core sees only our `Message` / `ToolSchema` / `AgentEvent`.
- **uv** — package + dependency management
- **pytest** — tests
- **ruff** — lint + format
- **mypy** — type checking

## Architecture

See `CLAUDE.md` § Architecture and § Project layout — the single source of truth for the layer breakdown, file tree, and folder rules. Update only there, never duplicate here.

## MVP scope (v0.1 — "it works")

- One provider: OpenAI-compatible
- Three tools: `Read`, `Write`, `Bash`
- One permission mode: ask-before-each-tool-call
- Minimal TUI: input box, scrolling transcript, tool-call display
- Single conversation, no persistence
- Streaming responses

## Explicitly out of scope for v0.1

Multiple providers, sub-agents, MCP, skills, benchmarks, web search, image input, session persistence, permission modes beyond "always ask", file diffing UI, sandboxing — all later.

## Testing strategy

Goal: fast, deterministic, no API keys required for normal CI.

- **`FakeProvider`** — hand-written test double for the provider interface; returns pre-scripted responses and tool calls. Used to drive the agent loop in tests.
- **Tools tested in isolation** — `Read`/`Write`/`Bash` use a real `tmp_path` (pytest fixture). No filesystem mocks.
- **TUI tested with Textual `Pilot`** — keypress/snapshot tests.
- **Integration tests** — full agent loop with `FakeProvider` simulating multi-turn conversations including tool calls.
- **Real-provider smoke tests** — hand-crafted JSON fixtures of expected responses. Run on-demand / nightly, not on every PR.

This forces the provider seam to be clean (because it must support a fake) and keeps CI fast.

## Error handling philosophy

Two tiers:

- **Tool errors are normal LLM input.** File not found, command exits non-zero, permission denied → return the error text as the tool result. Agent sees it, reacts, can retry. The loop does *not* halt.
- **System errors halt the turn.** Provider unreachable, rate limit, auth failure, internal bug → surface to user via the TUI, pause the loop, user chooses retry/edit/quit.
- **Ctrl-C** cleanly aborts the current turn and returns to the input prompt.

Rule: distinguish "failures the model should handle" from "failures the user must handle."

## Configuration

- **Secrets via env vars**: `OPENAI_API_KEY`, `OPENAI_BASE_URL` (optional — for OpenRouter, local llama.cpp, etc.).
- **Settings via TOML**: `~/.config/termcoder/config.toml` (paths via `platformdirs` for cross-platform correctness).
- **Per-project override**: `.termcoder.toml` in the current working directory takes precedence over the user config.
- **Precedence**: project config > user config > built-in defaults. No CLI flags at v0.1 — for a single-session REPL with a handful of settings, env vars + TOML cover persistence and per-shell overrides.
- **Settings**: `model`, `temperature`, `max_tokens`, `system_prompt`, `permission_mode`.

## Definition of done for v0.1

- `uv run termcoder` launches the TUI.
- User can ask it to read a file and write a modified version, with per-tool permission prompts.
- Code is typed (mypy clean), linted (ruff clean), and tested at the layer seams.
- README explains the architecture and how to add a tool / a provider.

## Build sequence

Roughly one PR per step. Each step lands behind green CI before the next starts. The order is dependency-driven — every step's tests can run against what's already merged. Check a box when the PR is merged on `main`.

- [x] **1. Core types, events, errors.** `types.py`, `events.py`, `errors.py`, plus the `src/termcoder/` package skeleton (`__init__.py`). Pure, no I/O — the contract everything else consumes.
- [x] **2. Provider seam.** `providers/protocol.py` plus `tests/fakes/fake_provider.py` with scripted `AgentEvent` streams. The Protocol takes a message list (including tool-role `ToolResult` messages) and yields `AgentEvent`s — nail the round-trip shape here so step 5 doesn't retrofit it. Design against the fake first.
- [x] **3. OpenAI-compatible provider.** Real streaming via the OpenAI SDK with `base_url` override, tested with hand-crafted fixtures (not the live API).
- [x] **4. Tools.** `tools/protocol.py`, `tools/registry.py`, then `read.py`, `write.py`, `bash.py`. Each tested in isolation with `tmp_path`. Errors return as text, not exceptions.
- [x] **5. Agent loop.** `agent/state.py`, `agent/prompt.py`, `agent/loop.py`, plus `tests/fakes/fake_permission.py` (auto-allow for tests). Integration tests with the FakeProvider + real tools driving multi-turn conversations including tool calls. One test covers mid-stream gating: the model streams a tool call, the loop pauses for the permission callable, then resumes.
- [x] **6. Headless wiring.** `permissions.py`, `config.py`, `composition.py`, `cli.py`, `logging.py`, plus `__main__.py` and the `[project.scripts]` entry so `uv run termcoder` resolves. End-to-end run via stdin/stdout — no TUI yet, but Ctrl-C cleanly aborts the current turn. Proves the wiring before adding the visible layer.
- [ ] **7. TUI.** `tui/app.py` and the three widgets (`transcript`, `input`, `permission_modal`). Textual `Pilot` smoke test.

README architecture notes ("how to add a tool / a provider") land in whichever step introduces the seam they describe; a final docs pass after step 7 closes the v0.1 definition of done.

## Roadmap shape (post-MVP, not committed)

Slots, not features — to be filled in once v0.1 is done:

- Additional providers (Anthropic adapter).
- Additional tools (Edit, Grep, ListDir, …).
- Permission modes (allowlist, auto-approve-safe, deny-list).
- Session persistence + resume.
- Sub-agents / parallel execution.
- Benchmarks harness.
- MCP / skills / plugins.
