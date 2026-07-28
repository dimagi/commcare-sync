# CommCare Data Pipeline documentation

CommCare Data Pipeline lets an organization export data from
[CommCare HQ](https://github.com/dimagi/commcare-hq/) into databases it owns,
schedule transformations and aggregations, and forward results to external
systems.

## User guides

- [Add a CommCare Project](users/add-commcare-project.md)
- [Add a CommCare Account](users/add-commcare-account.md)
- [Add a database](users/add-database.md)
- [Set up an export](users/set-up-export.md)
- [Schedule a materialized view refresh](users/schedule-materialized-view-refresh.md)
- [Forward data to DHIS2](users/forward-to-dhis2.md)
- [Forward data to a CommCare fixture](users/forward-to-commcare-fixture.md)
- [Understanding the statistics](users/understanding-statistics.md)
- [Checking the logs for a run](users/checking-run-logs.md)

## Admin guides

- [Add a new user](admin/add-user.md)
- [Reset a password](admin/reset-password.md)
- [Delete a user](admin/delete-user.md)
- [Add a CommCare HQ server](admin/add-commcare-server.md)
- [Download CommCare Data Pipeline logs](admin/download-pipeline-logs.md)
- [Install as a server](admin/server-install.md)

## Install and run

CommCare Data Pipeline ships as a single `commcare-sync` command that runs the
whole app — web server and task scheduler together — with no separate services
to configure.

```bash
uv tool install commcare-sync
```

<!-- prettier-ignore-start -->
> [!NOTE]
> `commcare-sync` is not yet published to PyPI. Until then, install it
> from a checkout with `uv tool install .` or run it in place with
> `uv run commcare-sync` — see [DEV_SETUP.md](../DEV_SETUP.md).
<!-- prettier-ignore-end -->

Run it for yourself, on your own computer:

```bash
commcare-sync --desktop
```

This opens a native window (or your browser, on Linux) pointed at a local copy
of the app, listening only on `127.0.0.1` on a free port it picks for you.
Closing the window shuts everything down.

Run it as a server other people connect to:

```bash
commcare-sync --server
```

This listens on `0.0.0.0:8000` by default (override with `--bind` and `--port`),
prints the URL to visit, and keeps running until you stop it with `Ctrl-C` or
`SIGTERM`. See [Install as a server](admin/server-install.md) for running it as
a systemd service behind a reverse proxy.

Both modes store the database, generated secrets, logs, and uploaded media in a
per-user data directory (`~/.local/share/commcare-sync/` on Linux) — pass
`--data-dir DIR` or set `COMMCARE_SYNC_DATA_DIR` to use a different one. The
first time you visit the app with no users yet, it sends you to `/setup/` to
create the admin account.

## Development

See [DEV_SETUP.md](../DEV_SETUP.md) for setting up a local development
environment.

## Production

See [Install as a server](admin/server-install.md) for running
`commcare-sync --server` as a systemd service behind a reverse proxy.
