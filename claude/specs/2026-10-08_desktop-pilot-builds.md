# Desktop Pilot Builds

Produce unsigned Windows and macOS builds of CommCare Data Pipeline that pilot
users can install and run as a desktop app.

This builds on the July design, `claude/specs/2026-07-09_single-stack-packaging.md`
on the `nh/proto-linux` branch. Its decisions stand: pywebview window, PyInstaller
`--onedir` bundles, Inno Setup on Windows, a supervised `qcluster` child process,
and a per-user data directory. Phase 1 of that design (SQLite and Django-Q2) is
on master. Phase 2 (the launcher) is implemented on `nh/proto-linux`, which is
based on an older Phase 1 and is 46 commits behind master. Phase 3 (packaging)
exists only as a draft plan.

This spec covers what is left, for the first milestone.

## Milestones

**Milestone 1: pilot builds (this spec).** Unsigned installers for product
managers and QA engineers, who are comfortable clicking through SmartScreen and
Gatekeeper warnings. Builds come from a manually triggered workflow and are
published as a GitHub prerelease.

**Milestone 2: public release (out of scope here).** Authenticode signing,
Apple signing and notarization, a `.dmg`, the wheel on PyPI, a tag-triggered
release workflow, a Windows Job Object so that a crashed launcher cannot orphan
its children, and a WebView2 bootstrapper.

Two things for milestone 2 have weeks of lead time and should be requested now:
an Authenticode code-signing certificate, and an Apple Developer account.

## Branches

```
master ← nh/dispatch ← nh/poll ← nh/ux ← nh/launcher (L) ← nh/desktop (D) ← nh/bundle (P)

spike (S): throwaway, branched from nh/proto-linux
```

`nh/dispatch`, `nh/poll` and `nh/ux` are in review. L depends on `nh/dispatch`
(`claim_run`, `reap_stale_runs`, the `TIMEOUT` status), and D's banner must fit
alongside `nh/poll`'s run notice. Building on the tip of the stack keeps the
history linear.

This spec is added by L's first commit and removed by P's last.

## L: `nh/launcher`

Server-mode launcher, testable on Linux without a window.

### Porting from `nh/proto-linux`

Cherry-pick the launcher commits, `99dae87d` to `6eec8a45`, onto `nh/ux`:

| Treatment        | Commits                                                                                                                                                                                                                                                         |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Carry into L     | platformdirs, data dir, secrets, settings overlay, WhiteNoise and waitress, removing the gunicorn extra, `Q_CLUSTER` tuning, startup maintenance, `main()` and supervisor, console script, single instance, setup page, admin from env vars, `collectstatic` at startup |
| Squash into the commit they fix | `b5b473a7`, `77a51b5f`, `92412a83`, `b777e5a7`, `6eec8a45`                                                                                                                                                                                          |
| Move to D        | `1aaf8e7c`, `bb00042a`, `cdd9557f`, `21966700`                                                                                                                                                                                                                  |
| Drop             | `024a3088` (superseded by `claim_run`); `e627d642`, `4bd3c749`, `a75623bd` (docs, deferred to the docs refresh)                                                                                                                                                |

### Rename `TIMEOUT` to `INTERRUPTED`

L's first commit after this spec. The status is already inaccurate on
`nh/dispatch`: `reap_stale_runs` gives it to runs whose worker was killed by
OOM, a signal or a reboot, not only to runs that hit the time limit. Desktop
mode adds another cause, closing the window.

- Rename the enum member and value, `TIMEOUT = 'timeout'` to
  `INTERRUPTED = 'interrupted'`, labelled "Interrupted", in both
  `apps/commcare/models.py` and `apps/exports/models.py`.
- Replace the `fa-clock` icon in `apps/exports/templatetags/exports_tags.py`
  (e.g. `fa-circle-stop`). Keep `text-warning`.
- Add the choices-only migrations. There is no production data to convert.
- Update docstrings in `apps/schedules/dispatch.py`, `checks.py` and
  `tasks.py`.

Behaviour does not change: `INTERRUPTED` is in `FAILED_STATUSES`, and
`claim_run` retries it once. The run log keeps the specific reason.

### Startup maintenance

Replace `nh/proto-linux`'s `maintenance.reap_stale_runs`, which marks runs
`FAILED`, with the reaper in `apps/schedules/tasks.py`. Give it an optional
`started_before` argument. The dispatcher keeps its default cutoff (the task
timeout plus `REAP_MARGIN`). The launcher passes now.

Run before the cluster starts, in this order:

```
migrate
→ collectstatic
→ ensure_dispatcher_schedule
→ reap_stale_runs(started_before=now)
→ clear_stale_queue_locks
→ ensure_admin_user
→ start the cluster
```

Reaping before clearing locks means every task delivered again finds its run
`INTERRUPTED`, so `claim_run` retries it once. That keeps the guarantee the
`schedules.E001` check exists for, at startup too. Other cases:

- A task taken off the queue whose run is still `QUEUED` starts normally.
- A run that finished but whose task was never acknowledged is skipped.
- A retry that is itself interrupted stays `INTERRUPTED` (`_can_retry`).
- The dispatcher's own task delivered again does no harm.

Reaping without an age cutoff is safe only because nothing else runs a cluster
against the same database. Single-instance detection enforces that between
launchers. A developer running `manage.py qcluster` with
`COMMCARE_SYNC_DATA_DIR` pointing at a launcher's data directory would break
it. Say so in the docstring, without a guard.

### Stopping the process tree

`nh/proto-linux`'s supervisor calls `terminate()`, then `kill()`, on the
`qcluster` child only. On Windows, `terminate()` kills the process instantly,
and its children survive it. So the Django-Q2 workers, and any
`commcare-export` they started, carry on after the window closes.
`nh/dispatch`'s `2f2990c4` kills `commcare-export` in a `finally` block that a
killed worker never reaches. The orphaned export keeps writing to the
warehouse, and on the next launch its run is reaped and retried alongside it.

When stopping, the supervisor collects the cluster's descendants with `psutil`,
terminates them all, waits, and kills any that are left
(`psutil.wait_procs`). Add `psutil` as a dependency. A crash of the launcher
itself is milestone 2 (Job Object).

### `Q_CLUSTER`

Add `poll: 1.0` and `save_limit_per: 'func'` to the stack's settings. The
stack's `timeout` (23h) and `retry` (24h), and its lack of `max_attempts`,
stay.

### Docs

A short README section on running `uv run commcare-sync --server`. The
server-install guide waits for the docs refresh.

### Tests

Launcher tests come over with their commits, rewritten where the redesign
touches them. New tests:

- `reap_stale_runs(started_before=...)` reaps every `STARTED` run, and leaves
  `QUEUED` runs alone.
- After startup maintenance, a task whose lock was cleared is delivered again
  and `claim_run` creates a retry linked by `retry_of`.
- The supervisor's stop leaves no descendant processes.
- The rename: labels, icon, `FAILED_STATUSES`, `claim_run`.

## D: `nh/desktop`

### Window

Carry over pywebview as a Windows and macOS dependency (`1aaf8e7c`), the
desktop window and Linux browser fallback (`bb00042a`), with the supervision
fix (`cdd9557f`) squashed into it.

### Confirmation on close

Handle the window's `closing` event instead of pywebview's `confirm_close`,
which always asks, with fixed wording. Waitress serves Django in the launcher's
process, so the handler queries the run models directly:

- No run in `ACTIVE_STATUSES`: close without asking.
- Otherwise, ask with `window.create_confirmation_dialog`, e.g. "An export is
  running. Closing CommCare Data Pipeline will stop it. It will start again
  when you next open the app." Answering No cancels the close.

Verify by hand on both platforms that a dialog can be shown from the `closing`
handler. Some backends, Cocoa especially, have had problems with it. If it
fails, the fallback is to set `confirm_close` only while a run is active, with
its fixed wording.

The Linux browser fallback cannot confirm. Closing a tab does not stop the
server.

### Failed-runs banner

Carry over `21966700`. Signed-in users land on `exports:home`, not the
dashboard, so failures while the app was closed would otherwise go unnoticed.
When porting:

- Count `RunBaseModel.FAILED_STATUSES`, so `INTERRUPTED` runs are included.
- Make sure its wording does not overlap `nh/poll`'s `#run-notice`, which
  covers only runs started from the current page.

### Tests

The window and banner tests come over with their commits. New unit tests for
the closing handler with a fake window: asks when runs are active, does not
ask when there are none, cancels the close on No. The real dialog is checked
by hand (see the QA checklist).

## S: spike

Throwaway, on a scratch branch from `nh/proto-linux`, run by a manually
triggered workflow on `windows-latest`, `macos-latest` and `macos-15-intel`.
It is done when we know:

1. A rough PyInstaller `--onedir` build boots in `--server` mode, migrates,
   and the dispatcher's first scheduled tick succeeds. That proves the
   migrations, including `0001_create_dispatcher_schedule`, are bundled.
2. A rough `--run-det` mode runs `commcare_export.cli.entry_point()`, with
   `--help` and with an export of a query file to an Excel file (the Data
   Export Tool's SQL writer does not know SQLite). The export uses the test
   project `corpora` on `www.commcarehq.org`
   (https://www.commcarehq.org/a/corpora/), with an API key stored as a
   repository secret.
3. Each SQL driver from the `postgres`, `mysql` and `odbc` extras imports. On
   macOS, ODBC is expected to need Microsoft's SQL Server driver installed
   separately. If so, the pilot guide says so.
4. On Windows, the `psutil` tree kill leaves no `qcluster`, worker or
   `commcare-export` processes behind.
5. The bundle size and cold-start time.

The output is a findings note (hidden imports, data files, surprises) that P
uses. The spike's code is not kept.

## P: `nh/bundle`

### `--run-det`

A hidden mode handled first in `main()`, before resolving the data directory,
which passes its arguments to `commcare_export.cli.entry_point()`. A frozen
bundle has no system Python, and `sys.executable` is the bundle. The export
runner (`_compile_export_command` in `apps/exports/runner.py`) builds
`[sys.executable, '--run-det', ...]` when `sys.frozen` is set, and starts with
`settings.COMMCARE_EXPORT` otherwise.

### Frozen defaults

- With no arguments, a frozen build starts in `--desktop` mode.
- The windowed build has no `stdout` (it is `None` on Windows), so the launcher
  logs only to `<data-dir>/logs/` when frozen.

### `packaging/commcare-sync.spec`

`--onedir`, windowed. Hidden imports and data files come from the spike's
findings, expected to include:

- `collect_submodules` for `apps`, `django_q`, `commcare_export` and the SQL
  drivers;
- `anymail`, which is referred to only by a dotted string in `EMAIL_BACKEND`;
- `templates/` and `static/`. The compiled `static/css/site.css` is committed,
  so the build does not need Node.

Built with the `postgres`, `mysql` and `odbc` extras.

### `packaging/smoke_test.py`

Starts the built program with `--server --port <free> --data-dir <tmp>` and
asserts:

- `/` answers 200 or 302;
- the SQLite database has the `run_due_schedules` schedule, and a successful
  task of it appears within about 90 seconds. A fresh database's schedule fires
  on the first tick, so nothing is seeded;
- `--run-det --help` exits 0;
- `<data-dir>/logs/` has no tracebacks;
- no processes are left after it stops.

### Windows installer

`packaging/windows/setup.iss` (Inno Setup):

- installs for the current user, without admin rights (`PrivilegesRequired=lowest`);
- adds a Start Menu shortcut and an uninstaller;
- leaves the data directory when uninstalling;
- has no WebView2 bootstrapper. Windows 10 and 11 ship WebView2, and the
  browser fallback covers machines without it;
- is unsigned.

### macOS app

PyInstaller's `.app`, with the ad-hoc signature PyInstaller adds, zipped with
`ditto -c -k --keepParent`. A plain `zip` breaks the symbolic links and
signatures inside the bundle. Two builds: Apple Silicon (`macos-latest`) and
Intel (`macos-15-intel`). `universal2` is not attempted, because it needs every
compiled dependency as a universal wheel.

### `.github/workflows/pilot-build.yml`

Triggered manually. A matrix of `windows-latest`, `macos-latest` and
`macos-15-intel` runs `uv sync` with the extras, PyInstaller, the smoke test,
and packaging. A final job publishes a GitHub prerelease tagged
`pilot-YYYYMMDD-<short sha>` with three downloads: the Windows installer, and
the Apple Silicon and Intel `.app` zips.

### Pilot guide and QA checklist

One page covering:

- installing on each platform, and getting past the warnings: SmartScreen's
  "More info → Run anyway"; on macOS 15 and later, System Settings → Privacy &
  Security → "Open Anyway", or `xattr -dr com.apple.quarantine`;
- where the data directory and logs are, and how to send logs;
- the ODBC driver note, if the spike confirms it.

A manual QA checklist, run on Windows and on both Macs:

- first-run setup page, then creating the admin;
- a real export into a scratch database;
- closing during a run: the confirmation appears; after relaunch the run is
  `INTERRUPTED` and a retry runs;
- closing with no active run: no confirmation;
- the failed-runs banner shows the interrupted run;
- launching a second time opens the running instance.

## Out of scope

- Everything listed under milestone 2.
- The server-install guide and the broader docs refresh.
- Auto-update.
- Settings and database export and import.
- Linux bundles. Linux runs from a checkout until the wheel ships.
