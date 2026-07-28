# Download CommCare Data Pipeline logs

Retrieve the shared `commcare-export` log to investigate run-time behaviour
beyond what individual export-run logs show. The pipeline exposes this single,
cross-run log through the application; deeper host-side logs (Django request
errors, task worker output, launcher startup) are not written to a file under
the data directory — see [Host-side logs](#host-side-logs) for where they
actually go.

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

Anything not written by `commcare-export` is not exposed through the app.
`commcare-sync` has no logging configuration for Django or the task worker
(django-q2), so their output — request errors, task tracebacks, general runtime
logging — is not written to a file at all; it goes to whatever captures the
process's stdout/stderr. Only two things land in files, both under
`<data-dir>/logs/` (`<data-dir>` is wherever `commcare-sync` was started with —
the default per-user data directory unless overridden by `--data-dir` or
`COMMCARE_SYNC_DATA_DIR`):

- `commcare_export.log` — the same shared export log described above (`LOG_DIR`
  points here).
- `launcher.log` — the launcher's own startup, shutdown, and task cluster
  supervision messages (not Django's or django-q2's).

Everything else is wherever the process's stdout ended up:

- Running `commcare-sync --server` directly in a terminal: its own stdout.
- Running it under the sample systemd unit in
  [Install as a server](server-install.md): `journalctl --user -u commcare-sync`
  (or without `--user` for a system unit).

<!-- prettier-ignore-start -->
> [!NOTE]
> Per-export-run logs are stored in the database and rendered in the
> app, not in `commcare_export.log`. Start with those for most
> investigations — see [Next steps](#next-steps).
<!-- prettier-ignore-end -->

## Next steps

- [Checking the logs for a run](../users/checking-run-logs.md) — for per-run
  export logs (most investigations start here).
