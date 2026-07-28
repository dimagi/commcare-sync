# Download CommCare Data Pipeline logs

Retrieve the shared `commcare-export` log to investigate run-time behaviour
beyond what individual export-run logs show. The pipeline exposes this single,
cross-run log through the application; deeper host-side logs (task worker
output, Django errors, launcher startup) live in the data directory of the
`commcare-sync` process running the pipeline.

## Prerequisites

- Superuser access to CommCare Data Pipeline (the **Download Logs** link only
  appears for users where `is_staff` and `is_superuser` are both true).
- For host-side logs: shell access to the machine running the pipeline.

## Download the shared export log from the app

1. Sign in as a superuser.
2. Click the hamburger menu in the top-right corner of any page.
3. Choose **Download Logs**.
4. Your browser saves `commcare_export.log` to your download directory.

The link points at `/exports/download/commcare-export-log/`. Loading that URL
directly works too, and returns `404` if the log file has not been created yet
(i.e. no export has run since the deployment was provisioned).

## What's in `commcare_export.log`

The file is produced by the `commcare-export` CLI itself, which the pipeline
invokes with `--log-dir <LOG_DIR>` for every run. Each run appends to the same
file, so it accumulates output across:

- Every export configuration the pipeline has executed.
- Every project, server, and database those configs target.
- Every retry, success, and failure.

Entries are tagged with timestamps and the standard Python logging levels
(`INFO`, `WARNING`, `ERROR`). This is the right log to consult when an export
run's own log is truncated, or when you need to compare behaviour across runs.

<!-- prettier-ignore-start -->
> [!NOTE]
> The shared log is not rotated by the application. On a busy deployment it
> can grow large; rotate it yourself (e.g. with `logrotate`) if that matters
> for your install.
<!-- prettier-ignore-end -->

## Host-side logs

Anything not written by `commcare-export` is not exposed through the app. To
investigate task worker behaviour, Django request errors, or launcher startup
issues, sign in to the host and look in the data directory of the running
`commcare-sync` process.

- The application's `LOG_DIR` (and every other log written by Django or the task
  worker) is `<data-dir>/logs/`, where `<data-dir>` is the directory
  `commcare-sync` was started with — the default per-user data directory unless
  overridden by `--data-dir` or `COMMCARE_SYNC_DATA_DIR`. See
  [Install as a server](server-install.md) for locating the data directory on a
  server install.
- The launcher itself (startup, shutdown, task cluster supervision) logs to
  `<data-dir>/logs/launcher.log`.

<!-- prettier-ignore-start -->
> [!NOTE]
> Per-export-run logs are stored in the database and rendered in the
> app, not in `commcare_export.log`. Start with those for most
> investigations — see [Next steps](#next-steps).
<!-- prettier-ignore-end -->

## Next steps

- [Checking the logs for a run](../users/checking-run-logs.md) — for per-run
  export logs (most investigations start here).
