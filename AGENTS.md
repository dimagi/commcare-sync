# Documentation for AI Coding Assistants

## Commands

* Run tests: `uv run pytest [path/to/file.py::TestClass::test_method]`
* Check typing: `uv run mypy apps/ commcare_sync/ *.py`
* Check linting: `uv run ruff check`
* Format: `uv run ruff format <path/to/file.py>`
* Sort imports `uv run ruff check --select I --fix <path/to/file.py>`

These commands assume the virtual environment in `.venv/` is activated.

## Tech Stack

See [pyproject.toml](pyproject.toml).

## Coding Style

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Skills

When creating AI skills for this project, add them to `.claude/skills/`. This format is compatible with both Cursor and Claude Code.
