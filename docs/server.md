# Run on a server

On your own computer, CommCare Data Pipeline runs as a desktop app and stops
when you close it. On a shared server it runs all the time, and your colleagues
open it in their browsers. This page is for the person who sets that up, and
assumes a Linux server and a terminal.

## Install and start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git,
then:

```shell
git clone https://github.com/dimagi/commcare-sync.git
cd commcare-sync
uv sync --extra postgres
uv run commcare-sync
```

Add `--extra mysql` or `--extra odbc` for MySQL or SQL Server. The app listens
on every address on port 8000. Pass `--port` to listen elsewhere, and `--bind`
to listen on one address only.

On the first start, the launcher prints a setup link. Open it in a browser on
the server itself to create the administrator account. The link only works from
the server, so that nobody else on the network can claim the account, and it
changes on every start. It is also in `logs/launcher.log` in the data directory.

To create the administrator without the setup page, for example when the server
has no browser, set `COMMCARE_SYNC_ADMIN_EMAIL` and
`COMMCARE_SYNC_ADMIN_PASSWORD` in the environment before the first start. Both
are read once and can be dropped afterwards.

## Keep it running

The launcher runs the web server and the task cluster that performs exports,
refreshes and forwarders. Keep it running with whatever your server uses for
services, such as a systemd unit that runs `uv run commcare-sync` from the
checkout. To stop it without a terminal, create a file named `stop` in the data
directory.

## Update

Stop the launcher, then in the checkout run `git pull` and `uv sync` with the
same extras as before, and start it again. Database changes are applied at
startup.

## The data directory

The app keeps its database, encryption keys, logs and uploaded files in
`~/.local/share/commcare-sync` for the user that runs it. Pass `--data-dir`, or
set `COMMCARE_SYNC_DATA_DIR`, to use another place. Back this directory up: the
encryption keys in it are the only way to read the stored passwords and API
keys.

The launcher writes to `logs/launcher.log` there, the web application to
`logs/app.log`, and the export tool to `logs/commcare_export.log`.

## Behind a reverse proxy

To serve the app over HTTPS, put it behind a reverse proxy such as nginx or
Caddy that terminates TLS, and:

- pass `--bind 127.0.0.1`, so that the proxy is the only way in;
- have the proxy pass the original `Host` header on, for nginx with
  `proxy_set_header Host $host`, or signing in fails its security check;
- set `COMMCARE_SYNC_BEHIND_PROXY=1`, so that the app trusts the proxy's
  `X-Forwarded-Proto` header;
- create the administrator from the environment variables above: the setup page
  is disabled behind a proxy.

The app answers to any host name by default. Set `COMMCARE_SYNC_ALLOWED_HOSTS`
to a comma-separated list to restrict it.

## Other settings

Any Django setting can be overridden in a file named `settings.py` in the data
directory. The file is run as code, so it must belong to the user that runs the
app and not be writable by anyone else. Two uses:

- Behind a proxy that serves HTTPS only, set `SESSION_COOKIE_SECURE = True` and
  `CSRF_COOKIE_SECURE = True`, so that browsers never send the cookies over
  plain HTTP, and have the proxy send the HSTS header.
- To let users reset their own passwords from the sign-in page, set
  `EMAIL_BACKEND` to Django's SMTP backend, the `EMAIL_HOST` settings for your
  mail server, and `DEFAULT_FROM_EMAIL`; see Django's
  [email settings](https://docs.djangoproject.com/en/stable/topics/email/).
  Without this, administrators reset passwords in the Admin Site; see
  [Manage users](manage-users.md).

The application database cannot be moved; it is always in the data directory.

## Next

- [Manage users](manage-users.md)
