<h3 align="center">termcoder</h3>

<p align="center">
  An open-source TUI coding agent in Python.<br>
  Built as a clean, modular foundation that's easy to read, extend, and benchmark against.
</p>

<p align="center">
  <a href="https://github.com/nattergabriel/termcoder/actions/workflows/ci.yml"><img src="https://github.com/nattergabriel/termcoder/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/nattergabriel/termcoder/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.13%2B-blue.svg" alt="Python 3.13+" /></a>
</p>

---

## Why

The coding-agent space is crowded with strong tools (Claude Code, OpenCode, Aider, ...). termcoder isn't competing on features. It's a deliberately small reference implementation: a foundation that's straightforward to read, extend, and benchmark against. If you want to study how a coding agent is structured, or fork one as a starting point, that's the goal.

## How it works

A small async loop routes user input to an LLM provider, dispatches tool calls through configurable permission checks, and streams typed events to the terminal — rich renders the assistant's output, prompt_toolkit drives input and inline confirms. Each layer (provider, tool, permission policy) is a swappable seam behind a `typing.Protocol`, wired together at a single composition root. The core runs against a hand-written `FakeProvider` in tests, so most of the codebase is testable with no network and no API key.

## Install (target for v0.1)

```bash
uv tool install termcoder        # or: pipx install termcoder
export OPENAI_API_KEY="..."
termcoder
```

Any OpenAI-compatible provider works (OpenAI, OpenRouter, local llama.cpp, …). Set `OPENAI_BASE_URL` accordingly.

## License

[MIT](LICENSE). Solo-maintained, best-effort response time.
