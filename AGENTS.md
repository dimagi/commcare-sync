# Documentation for AI Coding Assistants

## Commands

* Run tests: `pytest`
* Check typing: `mypy apps/ commcare_sync/ *.py`
* Check linting: `ruff check`
* Format: `ruff format <path/to/file.py>`
* Sort imports `ruff check --select I --fix <path/to/file.py>`

These commands assume the virtual environment in `.venv/` is activated.

## Tech Stack

See [pyproject.toml](pyproject.toml).

## Coding Style

See [CONTRIBUTING.md](CONTRIBUTING.md).
