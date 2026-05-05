# Documentation for AI Coding Assistants

## Project Overview

CommCare Data Pipeline is a web application that allows a single
organization with multiple users to manage a data pipeline that exports
data from [CommCare](https://github.com/dimagi/commcare-hq/) using the
[CommCare Data Export Tool](https://github.com/dimagi/commcare-export/)
into a database owned by the organization. There the data can be
aggregated and transformed. From the database it can be used by BI tools
like Power BI, Superset or Tableau. It can also be forwarded to APIs of
third-party reporting platforms like DHIS2, or forwarded back to
CommCare to provide reporting data to users.

## Commands

The project uses a virtualenv in `.venv/` managed with uv. Activate it
with `source .venv/bin/activate`. Alternatively use `uv run ...` before
commands.

- Python: `uv run python3 ...`
- Run tests: `uv run pytest [path/to/file.py::TestClass::test_method]`
- Check typing: `uv run mypy apps/ commcare_sync/ *.py`
- Check linting: `uv run ruff check`
- Format Python: `uv run ruff format <path/to/file.py>`
- Format HTML templates: `npx prettier --write <path/to/file.html>`
- Sort imports `uv run ruff check --select I --fix <path/to/file.py>`

## Project Structure

### Configuration

| File                        | Purpose                                 |
|-----------------------------|-----------------------------------------|
| `commcare_sync/settings.py` | Main Django settings                    |
| `commcare_sync/urls.py`     | Root URL configuration                  |
| `commcare_sync/celery.py`   | Celery task queue configuration         |
| `pyproject.toml`            | Python dependencies, tool configuration |
| `package.json`              | JavaScript dependencies, build scripts  |

### Applications (`apps/`)

| App           | Purpose                                      |
|---------------|----------------------------------------------|
| `commcare/`   | CommCare server, account, and project models |
| `exports/`    | Export configurations and execution          |
| `forwarding/` | Data forwarding rules                        |
| `schedules/`  | Scheduling and periodicity logic             |
| `users/`      | Custom user model, authentication            |
| `web/`        | Landing pages, context processors            |

### Templates (`templates/`)

| Path                    | Purpose                                          |
|-------------------------|--------------------------------------------------|
| `web/base.html`         | Base template (loads Alpine.js, HTMX, Bootstrap) |
| `web/app/app_base.html` | Base for authenticated app pages                 |
| `web/components/`       | Reusable components (nav, messages, run buttons) |
| `{app}/partials/`       | HTMX partial templates per app                   |

### Static Files (`static/`)

| Path               | Purpose                                 |
|--------------------|-----------------------------------------|
| `js/alpine.min.js` | Alpine.js framework                     |
| `js/htmx.min.js`   | HTMX library                            |
| `css/site.css`     | Compiled from `assets/styles/site.scss` |

### Testing

| Path                             | Purpose                                   |
|----------------------------------|-------------------------------------------|
| `apps/{app}/tests/`              | Tests per application                     |
| `apps/exports/tests/conftest.py` | Pytest and Playwright configuration       |
| `apps/exports/tests/fixtures.py` | Reusable test data fixtures               |
| `apps/exports/tests/helpers.py`  | Test helper functions (login, navigation) |

### Agent documentation

| Path                                     | Purpose              |
|------------------------------------------|----------------------|
| `claude/specs/YYYY-MM-DD_spec-name.md`   | Design specs         |
| `claude/plans/YYYY-MM-DD_plan-name.md`   | Implementation plans |
| `claude/reviews/YYYY-MM-DD_plan-name.md` | Code reviews         |

### Key Patterns

- **HTMX partials**: Templates in `{app}/partials/` return HTML fragments
  for partial page updates
- **Alpine.js**: Reactive state via `x-data`, `x-model`, `@change`
  attributes in templates
- **Celery tasks**: Defined in `{app}/tasks.py`, configured in
  `commcare_sync/celery.py`
- **Playwright tests**: Use `page.evaluate("htmx.trigger(...)")` to
  trigger HTMX events, as `select_option()` doesn't fire Alpine
  `@change` handlers

## Coding Style

See [CONTRIBUTING.md](CONTRIBUTING.md)
