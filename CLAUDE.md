# Documentation for AI Coding Assistants

## Project Overview

CommCare Data Pipeline is a web application that allows a single organization
with multiple users to manage a data pipeline that exports data from
[CommCare](https://github.com/dimagi/commcare-hq/) using the
[CommCare Data Export Tool](https://github.com/dimagi/commcare-export/) into a
database owned by the organization. There the data can be aggregated and
transformed. From the database it can be used by BI tools like Power BI,
Superset or Tableau. It can also be forwarded to APIs of third-party reporting
platforms like DHIS2, or forwarded back to CommCare to provide reporting data to
users.

## Commands

Run commands in the uv virtualenv using `uv run ...`.

- Python: `uv run python3 ...`
- Run tests: `uv run pytest [path/to/file.py::TestClass::test_method]`
- Check typing: `uv run mypy apps/ commcare_sync/ *.py`
- Check linting: `uv run ruff check`
- Format Python: `uv run ruff format <path/to/file.py>`
- Format HTML and Markdown: `npx prettier --write <path/to/file.html>`
- Sort imports `uv run ruff check --select I --fix <path/to/file.py>`

## Project Structure

### Agent documentation

| Description          | Path                                        |
| -------------------- | ------------------------------------------- |
| Design specs         | `claude/specs/YYYY-MM-DD_spec-name.md`      |
| Implementation plans | `.claude/plans/YYYY-MM-DD_plan-name.md`     |
| Code reviews         | `.claude/reviews/YYYY-MM-DD_review-name.md` |

Specs are committed before implementation starts and removed after
implementation is complete. Plans and reviews are artifacts specifically for
Claude, and they are stored under `.claude/` because Git ignores the directory.

### Configuration

| Description                                 | File                              |
| ------------------------------------------- | --------------------------------- |
| Main Django settings                        | `commcare_sync/settings.py`       |
| Git-ignored local settings                  | `commcare_sync/settings_local.py` |
| Root URL configuration                      | `commcare_sync/urls.py`           |
| Django Q2 task queue settings (`Q_CLUSTER`) | `commcare_sync/settings.py`       |

### Applications (`apps/`)

| Description                                  | App           |
| -------------------------------------------- | ------------- |
| CommCare server, account, and project models | `commcare/`   |
| Export configurations and execution          | `exports/`    |
| Data forwarding rules                        | `forwarding/` |
| Scheduling and periodicity logic             | `schedules/`  |
| Custom user model, authentication            | `users/`      |
| Landing pages, context processors            | `web/`        |

### Templates (`templates/`)

| Description                                      | Path                    |
| ------------------------------------------------ | ----------------------- |
| Base template (loads Alpine.js, HTMX, Bootstrap) | `web/base.html`         |
| Base for authenticated app pages                 | `web/app/app_base.html` |
| Reusable components (nav, messages, run buttons) | `web/components/`       |
| HTMX partial templates per app                   | `{app}/partials/`       |

### Static Files (`static/`)

| Description                             | Path           |
| --------------------------------------- | -------------- |
| Compiled from `assets/styles/site.scss` | `css/site.css` |

### Testing

| Description                               | Path                           |
| ----------------------------------------- | ------------------------------ |
| Tests per application                     | `apps/{app}/tests/`            |
| Pytest and Playwright configuration       | `apps/{app}/tests/conftest.py` |
| Reusable test fixtures                    | `apps/{app}/tests/fixtures.py` |
| Test helper functions (login, navigation) | `apps/{app}/tests/helpers.py`  |
| Test fixtures reusable across apps        | `tests/fixtures.py`            |

### Key Patterns

- **Bootstrap**: Where Bootstrap can achieve the same functionality as
  Alpine.js, use Bootstrap.
- **HTMX partials**: Templates in `{app}/partials/` return HTML fragments for
  partial page updates
- **Alpine.js**: Reactive state via `x-data`, `x-model`, `@change` attributes in
  templates
- **Django Q2 tasks**: Defined as plain callables in `{app}/tasks.py`,
  dispatched with `async_task()` from `django_q.tasks`
- **Playwright tests**: Use `page.evaluate("htmx.trigger(...)")` to trigger HTMX
  events, as `select_option()` doesn't fire Alpine `@change` handlers

## Coding Style

See [CONTRIBUTING.md](CONTRIBUTING.md)
