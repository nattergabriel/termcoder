# termcoder

[![CI](https://github.com/nattergabriel/termcoder/actions/workflows/ci.yml/badge.svg)](https://github.com/nattergabriel/termcoder/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)

An open-source TUI coding agent in Python — built as a clean, modular foundation that's easy to read, extend, and benchmark against.

> **Status: pre-v0.1.** Architecture and scope are defined; code is in active development. See [PLAN.md](PLAN.md) for the working spec.

## Install (target for v0.1)

```bash
uv tool install termcoder        # or: pipx install termcoder
export OPENAI_API_KEY="..."
termcoder
```

Any OpenAI-compatible provider works (OpenAI, OpenRouter, local llama.cpp, …) — set `OPENAI_BASE_URL` accordingly.

## License

[MIT](LICENSE). Solo-maintained — best-effort response time.
