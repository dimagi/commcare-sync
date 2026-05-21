# Download CommCare Data Pipeline logs

Retrieve the shared `commcare-export` log to investigate run-time behaviour
beyond what individual export-run logs show. The pipeline exposes this single,
cross-run log through the application; deeper host-side logs (Celery worker
output, Django errors, system logs) live on the server and are managed by the
Ansible deployment.

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
> The shared log is not rotated by the application. On a busy
> deployment it can grow large. Production deployments managed via
> Ansible typically rotate it via `logrotate` — see the
> [Ansible deployment docs](https://commcare-sync-ansible.readthedocs.io/en/latest/system-administration.html)
> for details.
<!-- prettier-ignore-end -->

## Host-side logs

Anything not written by `commcare-export` is not exposed through the app. To
investigate Celery worker behaviour, Django request errors, runserver output, or
system-level issues, sign in to the host and look at the deployment's log
directory.

- The application's `LOG_DIR` defaults to `<project root>/logs/`. The Ansible
  deployment overrides this; consult the
  [Ansible system administration guide](https://commcare-sync-ansible.readthedocs.io/en/latest/system-administration.html)
  for the configured path and for rotation, retention, and access conventions.
- Celery workers, the Django app server, and the scheduler each emit their own
  logs to the locations the Ansible playbook configures.

<!-- prettier-ignore-start -->
> [!NOTE]
> Per-export-run logs are stored in the database and rendered in the
> app, not in `commcare_export.log`. Start with those for most
> investigations — see [Next steps](#next-steps).
<!-- prettier-ignore-end -->

## Next steps

- [Checking the logs for a run](../users/checking-run-logs.md) — for per-run
  export logs (most investigations start here).
