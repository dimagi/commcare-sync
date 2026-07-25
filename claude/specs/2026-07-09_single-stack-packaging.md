# Single-Stack Packaging

Replace the Postgres + Redis + Celery stack with SQLite + Django-Q2 across all
deployments, and package the application so it installs as a desktop app on
Windows/macOS, and as a single `uv tool install` command on Linux and servers.

## Goals

- One stack for every deployment: SQLite app database, Django-Q2 task runner,
  one OS process.
- Desktop mode: double-click app on Windows/macOS opens the UI in an embedded
  webview window; on Linux it opens the system browser.
- Server mode: the same entry point serves a port for a small multi-user
  installation (2–3 concurrent users at most).
- Remove Docker, Ansible, Postgres, Redis, Celery, and nginx from the
  installation requirements.

## Non-goals

- Scale beyond a handful of concurrent users. SQLite in WAL mode is the
  ceiling by design.
- Background syncing while the desktop app is closed. Scheduled exports run
  only while the process runs; overdue schedules catch up on next launch.
- Bundled TLS. Server installs that need HTTPS put a reverse proxy
  (Caddy/nginx) in front.
- Settings/DB export-import. Follow-up feature; it doubles as the migration
  path for existing Postgres deployments (`dumpdata`/`loaddata`).

## Architecture

One codebase, one process, two entry modes:

```
commcare-sync [--desktop | --server [--bind ADDR] [--port N]] [--data-dir DIR]
└── launcher (Python)
    ├── migrate SQLite app DB (WAL mode, busy_timeout)
    ├── thread: waitress serving Django
    │     desktop: 127.0.0.1:<random free port>
    │     server:  configured bind/port (default 0.0.0.0:8000)
    ├── threads: Django-Q2 cluster (workers + scheduler, ORM broker)
    └── desktop only: pywebview window (Windows/macOS)
        or webbrowser.open() (Linux); server: runs until SIGTERM
```

- `--desktop` is the default in the packaged Windows/macOS build (no args when
  double-clicked).
- Desktop exits when the window closes. Server mode is systemd-friendly:
  logs to stdout, handles SIGTERM; docs ship a sample systemd unit.

### Stack changes

Removed dependencies: `celery[redis]`, `django-celery-beat`,
`celery-progress`, `gunicorn`. Added: `django-q2`, `waitress`, `pywebview`
(Windows/macOS builds), `whitenoise`, `platformdirs`.

- Tasks in `apps/*/tasks.py` are rewritten directly as Django-Q2 tasks. No
  dispatch abstraction: Q2 is the only runner.
- The `schedules` app's periodicity logic remains the source of truth and
  feeds Django-Q2's scheduler instead of celery-beat.
- The run-progress UI (currently `celery-progress`) becomes HTMX polling
  against Q2 task state in the ORM.
- `psycopg` stays as a dependency, but only for *warehouse* connections
  (`apps/refreshes/`), never for the app DB. `refreshes` continues to require
  a remote Postgres warehouse. DET (`commcare-export`) continues to write to
  the remote org database; the local SQLite file holds only application state.
- WhiteNoise serves static files in both modes, removing the nginx static
  requirement.

### Concurrency

SQLite in WAL mode with a `busy_timeout` handles 2–3 users plus the worker
threads; app-DB writes are short (task state, run logs). Heavy writes go to
the remote warehouse. If a busy instance hits `database is locked`, the remedy
is queue tuning, not a database swap.

## CLI, data locations, lifecycle

### Data directory

All mutable state lives in a per-user data directory via `platformdirs`
(`%LOCALAPPDATA%\commcare-sync\` on Windows,
`~/Library/Application Support/commcare-sync/` on macOS,
`~/.local/share/commcare-sync/` on Linux), overridable with `--data-dir`:

```
<data-dir>/
├── db.sqlite3          # app DB
├── settings.py         # optional local overrides (replaces settings_local.py)
├── logs/               # rotating app + DET run logs
├── media/              # DET query files, as today
└── secrets             # generated SECRET_KEY and FERNET_KEYS
```

The whole directory is the instance state — the future export/import feature
is "copy this directory", including the Fernet keys, without which the
encrypted credentials in `apps/db` and `apps/forwarding` are unreadable.

### First run

- Generate `SECRET_KEY` and an initial `FERNET_KEYS` list (one key, same
  `Fernet.generate_key()` logic as `./fernet-gen`). The list format preserves
  the existing rotation scheme (`FERNET_KEYS[0]` encrypts, older keys
  decrypt).
- Run `migrate` automatically on every startup before serving.
- With zero users in the DB, serve a one-time setup page (create admin
  account) instead of the login page. Server mode alternatively accepts
  `COMMCARE_SYNC_ADMIN_EMAIL` / `COMMCARE_SYNC_ADMIN_PASSWORD` env vars for
  non-interactive provisioning.

### Lifecycle

- Desktop: closing the window triggers graceful shutdown; Q2 workers finish
  or abandon the current task. Q2 acknowledges (deletes) a task's queue row
  only on completion, so a task abandoned mid-run is **not** retried on next
  launch. With the ORM broker (`django_q/brokers/orm.py`), `dequeue()` sets
  the row's `lock` to `now + Conf.RETRY` when it hands the task to a
  worker; the row only becomes eligible for redelivery once that lock
  expires — i.e. 8 hours later given this project's `retry: 8h`, not "on
  next launch" as previously assumed here. A worker-side timeout is
  enforced by `process.terminate()` on the worker process
  (`django_q/cluster.py`), which kills the task with no in-process
  exception, so nothing inside the task gets a chance to mark its own DB
  row as failed. See the note under "Verification of key assumptions"
  below for the consequence this has for `RefreshRun`/`ExportRun`/etc. rows
  and why a Phase 2 reaper is needed.
- Single instance: the launcher writes a port file in the data dir; a second
  launch detects a live instance and opens the existing URL instead of
  starting a second process.
- Server: standard signal handling; port conflicts fail fast with a clear
  message (desktop picks another free port).

## Auth and security

Both modes keep normal Django auth — no auto-login in desktop mode. One code
path, existing user model and roles, and a laptop app holding org database
credentials should not be open to whoever sits at the machine. Desktop mode
sets a long session age so login is rare. Signup stays invite-only; admins
create user accounts.

- Desktop: bind `127.0.0.1` only; `ALLOWED_HOSTS = ['127.0.0.1',
  'localhost']`; CSRF trusted origins pinned to the local port; `DEBUG` off in
  packaged builds.
- Server: `ALLOWED_HOSTS` from env/config; plain HTTP with documented
  reverse-proxy-for-TLS recommendation; `SECURE_PROXY_SSL_HEADER` support so
  cookies get the Secure flag behind a proxy.

## Packaging

### PyPI package (Linux desktop + all servers)

- Console-script entry point `commcare-sync`.
- Wheel includes templates, compiled static files (SCSS build output built in
  CI), and app assets so `uv tool install commcare-sync` works standalone.

### PyInstaller bundles (Windows + macOS)

One spec file in the repo, `--onedir` mode (`--onefile` unpacks to temp on
every launch: slow start, antivirus friction). Known Django friction handled
explicitly:

- Hidden imports declared for string-loaded apps (`INSTALLED_APPS`), Q2,
  waitress.
- Templates, static files, DET query assets, and per-app migrations bundled
  as data files (PyInstaller misses migrations without hooks).
- DET invocation: there is no system Python on the target machine, and
  `sys.executable` inside a PyInstaller bundle re-enters our EXE, so the
  launcher gains an internal `--run-det` entry mode that the app uses to run
  `commcare-export` as a subprocess of the bundle itself.

### Installers

- Windows: Inno Setup → signed `commcare-sync-setup.exe`. Code-signing
  certificate to be procured by the org.
- macOS: `.app` in a `.dmg`, signed and notarized. Apple Developer account
  required.
- Linux: no bundle; `uv tool install commcare-sync` is the documented path.
  (Embedded webview is deliberately not offered on Linux: it would require
  system WebKitGTK, which varies by distro; the system browser avoids the
  dependency entirely.)

### CI

GitHub Actions release workflow: build wheel → publish to PyPI; build
PyInstaller bundles on `windows-latest` and `macos-latest` → attach installers
to the GitHub release. Each platform runs a smoke test that boots the bundle,
requests `http://127.0.0.1:<port>/`, and asserts a 200 before packaging.

## Error handling and observability

- Task failures (DET runs, forwarding, refreshes): Q2 stores results in the
  ORM; the existing run-history UI reads from there. Failed scheduled runs
  surface as a banner in the UI on next open — in desktop mode nobody tails
  logs.
- The launcher supervises the Q2 cluster and restarts it on crash (bounded
  retries), logging to `<data-dir>/logs/`.
- The existing "download pipeline logs" admin feature reads from the data-dir
  log location.
- Sentry: optional DSN via env/config; off by default in desktop builds.

## Testing

- Existing pytest + Playwright suites run on SQLite; anything
  Postgres-assuming is fixed as part of the Celery removal.
- New tests: launcher units (port selection, single-instance detection,
  first-run key generation), a Q2 integration test through the ORM broker,
  and a Playwright test for the first-run setup page.
- The per-platform CI smoke test of the PyInstaller bundle guards against
  freezing regressions (missing hidden imports are invisible to unit tests).

## Migration for existing deployments

Existing Postgres + Celery installations migrate once via
`dumpdata`/`loaddata` into a fresh data directory, carrying over their
existing `FERNET_KEYS`. The export/import follow-up feature productizes this
path; until then it is a documented manual procedure.

**Known defect (found during Phase 1 review, unresolved):** this path does
not currently work as stated. A `dumpdata` taken from a pre-branch (Celery +
`django_celery_beat`) database includes a `periodic_task` field on the
`ExportConfig`/`MultiProjectExportConfig`/`ForwardingConfig`/`RefreshConfig`
fixtures, referencing `django_celery_beat.PeriodicTask` rows. Neither that
field nor that model exists after this branch, so `loaddata` rejects the
dump outright. Fold a fixup step (or a documented `jq`/script transform
that drops the stale field and backfills `schedule_enabled`/`next_run_at`)
into the export/import follow-up feature.

## Open questions

None — decisions above were settled during design review on 2026-07-09.

## Verification of key assumptions (during implementation)

- Django-Q2 scheduler catch-up semantics for schedules missed while the app
  was closed; add a "run overdue now" nudge if it does not catch up on start.
- Django-Q2 retry semantics for tasks interrupted by shutdown: **verified
  during Phase 1 review, and the semantics are not what this spec
  originally assumed.** See the corrected Lifecycle section above. In
  short: with the ORM broker and this project's `retry: 8h`, an abandoned
  task is redelivered 8 hours after it was dequeued, not "on next launch";
  and a worker timeout kills the process directly (`process.terminate()`),
  so a task's own exception-handling code never runs and never gets to
  mark its DB row as failed.
- pywebview + WebView2 behavior on a clean Windows 10 machine (WebView2 is
  preinstalled on current Windows 10/11 builds; the Inno Setup installer can
  bootstrap it if absent).

## Phase 2 follow-up: stale STARTED run reaper

A direct consequence of the retry semantics above: a run interrupted by
worker timeout (`Q_CLUSTER['timeout']`) or by process shutdown/kill leaves
its `RefreshRun`/`ExportRun`/`ForwardingRun`/etc. row stuck in `STARTED`
(or `QUEUED`) forever — nothing marks it FAILED, because the worker
process is killed rather than raising inside the task. Since
`run_scheduled_*_task` skips any config with an active
(`QUEUED`/`STARTED`) run, and `has_active_run` blocks the UI's Run button,
**one timed-out or shutdown-interrupted run permanently disables that
config's schedule and its manual Run button**, with no expiry.

This was tolerable for Phase 1 (closing the app was rare and Celery didn't
have this failure mode in the same shape), but Phase 2 needs a stale-run
reaper: on cluster start, mark any `STARTED` run older than
`Q_CLUSTER['timeout']` as `FAILED` (with a log line noting the
abandonment) so its config becomes runnable again. "Closing the window
abandons the current task" becomes a routine lifecycle event once desktop
packaging ships, so this can't stay a manual cleanup step.
