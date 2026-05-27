<h3 align="center">termcoder</h3>

<p align="center">
  An open-source terminal coding agent in Python.<br>
  Small enough to understand, useful enough to run on a real project.
</p>

<p align="center">
  <a href="https://github.com/nattergabriel/termcoder/actions/workflows/ci.yml"><img src="https://github.com/nattergabriel/termcoder/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/nattergabriel/termcoder/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.13%2B-blue.svg" alt="Python 3.13+" /></a>
</p>

---

## What it is

termcoder is a local terminal coding agent and a readable reference implementation of one. It is built to be useful on real projects while staying small enough that the full agent loop, provider layer, tool system, permission flow, and TUI can be understood without digging through a large framework.

The goal is not to out-feature mature tools like Claude Code, Codex, or OpenCode. It is a focused open-source project for learning, experimentation, and demonstrating how a practical coding-agent harness can be designed.

## Features

- Ask for code changes or codebase explanations from a terminal chat.
- Watch streamed responses and live tool-call status while the agent works.
- Let the agent read, list, search, create, edit, move, and delete files, and run project commands.
- Choose the approval style that fits the task: confirm every action, auto-allow read-only inspection, or run fully trusted.
- Use OpenAI, Anthropic, or an OpenAI-compatible endpoint such as OpenRouter or a local server.
- Give the agent project-specific guidance with `AGENTS.md` files inherited from parent directories.
- Add reusable local Agent Skills and activate them inline with `/skill-name`.
- Switch provider, model, and temperature during a session with slash commands.

## Run from source

```bash
uv sync
export OPENAI_API_KEY="..."
uv run termcoder
```

To use Anthropic instead:

```bash
export ANTHROPIC_API_KEY="..."
uv run termcoder
/provider anthropic
/model <anthropic-model>
```

OpenAI-compatible providers such as OpenRouter or local llama.cpp servers can be used by setting `OPENAI_BASE_URL`.

## Configuration

Configuration starts with built-in defaults, then applies `~/.config/termcoder/config.toml`, then `.termcoder.toml` in the project. Project settings override user settings. API keys and base URLs stay in environment variables.

```toml
provider = "openai"
model = "gpt-4o-mini"
temperature = 0.7
permission_mode = "ask_each"
max_iterations = 25
```

Supported `permission_mode` values are `ask_each`, `allow_readonly`, and `allow_all`.

## Development

```bash
uv run ruff check
uv run ruff format --check
uv run mypy .
uv run pytest
```

The main contract is the typed `AgentEvent` stream produced by `agent/loop.py` and consumed by the REPL. Providers and tools adapt at the edges; the agent core works with internal domain types instead of vendor SDK objects.

## License

[MIT](LICENSE).
