# Developer setup

This is the development setup for CommCare Data Pipeline. There are no external
services to run — the app database is a local SQLite file, and the task queue
runs against that same database. `manage.py runserver` and `manage.py qcluster`
both run natively.

For production setup, see [Install as a server](docs/admin/server-install.md).

## Prerequisites

- Linux or macOS (on Windows, use WSL2 with Ubuntu)
- [Python 3.12 or newer (and older than 3.15)](https://www.python.org/) —
  matches `requires-python` in `pyproject.toml`
- [uv](https://docs.astral.sh/uv/) for Python dependency management
- [Node.js](https://nodejs.org/) and `npm` for the frontend assets

## Clone and install

```bash
git clone git@github.com:dimagi/commcare-sync.git
cd commcare-sync
uv sync
npm install
```

## Configure `SECRET_KEY` and `FERNET_KEYS`

Django's `SECRET_KEY` and the `FERNET_KEYS` used to encrypt CommCare credentials
must be set before the app will run. See the comment near the top of
`commcare_sync/settings.py` for the full details. You can either export them as
environment variables or set them in a `commcare_sync/settings_local.py` file
you create yourself.

Generate a `SECRET_KEY`:

```bash
openssl rand -base64 48
```

Generate a Fernet key:

```bash
./fernet-gen
```

## First-time database setup

```bash
uv run python3 manage.py migrate
uv run python3 manage.py createsuperuser
```

This creates `db.sqlite3` in the repo root.

## Running the app

```bash
uv run python3 manage.py runserver 0.0.0.0:8001
```

Run the task worker and scheduler in a second terminal:

```bash
uv run python3 manage.py qcluster
```

The app is now at <http://127.0.0.1:8001/>. The app database is a local SQLite
file (`db.sqlite3`); no database or message-broker service is required. If you
want your exports and refreshes to write somewhere real, add a database
connection through the app itself — see
[Add a database](docs/users/add-database.md) — pointing at whatever warehouse
database (Postgres, MySQL, SQL Server, …) you already have available; this is
independent of the app's own SQLite database.

## Trying the packaged entry point

The `commcare-sync` console script (what a real install runs) also works from a
checkout, if you want to try it without the `runserver`/`qcluster` split:

```bash
uv run commcare-sync --server --data-dir /tmp/whatever
```

Point `--data-dir` at a scratch directory — it holds its own `db.sqlite3`,
generated secrets, and logs, separate from the `runserver`/`qcluster` setup
above. This is a convenience for trying the launcher locally; the `runserver` +
`qcluster` flow above remains the primary way to develop.

## Front-end assets

The compiled CSS/JS are checked in, but if you're working on stylesheets or
JavaScript you'll want a watcher:

```bash
npm run dev-watch
```

To build production assets once:

```bash
npm run build
```

## Running tests

```bash
uv run pytest
```

Playwright browsers must be installed once:

```bash
uv run playwright install
```

On Ubuntu, install Playwright's required OS packages with
`uv run playwright install --with-deps`. On other distributions, install the
equivalents of: `libicu`, `libxml2`, `libgstreamer-plugins-bad1.0-0`,
`libflite1`, `libmanette-0.2-0`, `libwoff1`, `gstreamer1.0-libav`.

Useful Playwright invocations:

```bash
uv run pytest apps/exports/tests/test_run_button_playwright.py --headed
uv run pytest apps/exports/tests/test_run_button_playwright.py --headed --slowmo 1000
PWDEBUG=1 uv run pytest apps/exports/tests/test_run_button_playwright.py
```

## Common tasks

| Task             | Command                                 |
| ---------------- | --------------------------------------- |
| Format Python    | `uv run ruff format <path>`             |
| Sort imports     | `uv run ruff check --select I --fix`    |
| Lint Python      | `uv run ruff check`                     |
| Type check       | `uv run mypy apps/ commcare_sync/ *.py` |
| Format templates | `npx prettier --write <path>.html`      |

## Troubleshooting

<!-- prettier-ignore-start -->
> [!NOTE]
> **`SECRET_KEY` or `FERNET_KEYS` not set** — `runserver` and `qcluster`
> read these from the environment or `commcare_sync/settings_local.py`. See
> the "Configure `SECRET_KEY` and `FERNET_KEYS`" section above.
<!-- prettier-ignore-end -->
