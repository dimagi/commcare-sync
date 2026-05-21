# Developer setup

This is the development setup for CommCare Data Pipeline. Postgres and Redis run
in Docker; Celery and the Django runserver run natively so they're easy to
attach a debugger to. Everything lives in a single `tmux` session.

For production setup, see
<https://commcare-sync-ansible.readthedocs.io/en/latest/system-administration.html>.

## Prerequisites

- Linux or macOS (on Windows, use WSL2 with Ubuntu)
- [Python 3.12 or newer (and older than 3.15)](https://www.python.org/) —
  matches `requires-python` in `pyproject.toml`
- [uv](https://docs.astral.sh/uv/) for Python dependency management
- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [tmux](https://github.com/tmux/tmux/wiki)
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

The Docker services in `docker-compose.yml` read these from `.env.dev`, but the
natively-run runserver and Celery worker read them from the environment or from
`commcare_sync/settings_local.py`.

## First-time database setup

The host ports for Postgres (`5433`) and Redis (`6380`) are deliberately offset
in `docker-compose.yml` so they don't clash with a CommCare HQ checkout running
on the same machine.

```bash
source .venv/bin/activate
docker-compose up -d db redis
./manage.py migrate
./manage.py createsuperuser
docker-compose down
```

## Run the stack in tmux

Save the following script as `run_dev.sh` in the repo root, make it executable
with `chmod +x run_dev.sh`, and run it.

```bash
#!/bin/bash

tmux new-session -s ccsync  -n docker ' \
        source .venv/bin/activate; \
        docker-compose up db redis' \; \
    new-window -n worker ' \
        source .venv/bin/activate; \
        sleep 2s; \
        celery -A commcare_sync worker -l INFO -B' \; \
    new-window -n runserver ' \
        source .venv/bin/activate; \
        sleep 2s; \
        ./manage.py runserver 0.0.0.0:8001' \;
```

This opens a `tmux` session named `ccsync` with three windows:

- `docker` — Postgres and Redis via Docker Compose.
- `worker` — Celery worker, with embedded beat scheduler (`-B`).
- `runserver` — Django dev server on <http://127.0.0.1:8001/>.

Reattach later with `tmux attach -t ccsync`. Tear it all down with
`tmux kill-session -t ccsync` (which stops Celery and runserver) followed by
`docker-compose down`.

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
> **Port already in use** — If `docker-compose up` complains about port `5433`
> or `6380` already being bound, you likely have something else listening on
> those ports. Stop them, or change the host ports in `docker-compose.yml`.
<!-- prettier-ignore-end -->

<!-- prettier-ignore-start -->
> [!NOTE]
> **`runserver` can't connect to the database** — Make sure the `docker` tmux
> window is healthy. Postgres takes a few seconds to start; the `sleep 2s` in
> the script handles the common case but not slow machines.
<!-- prettier-ignore-end -->

<!-- prettier-ignore-start -->
> [!NOTE]
> **`SECRET_KEY` or `FERNET_KEYS` not set** — The runserver and Celery worker
> read these from the environment or `commcare_sync/settings_local.py`. See
> the "Configure `SECRET_KEY` and `FERNET_KEYS`" section above.
<!-- prettier-ignore-end -->
