# Install as a server

Run CommCare Data Pipeline as a long-lived service for multiple users, using the
packaged `commcare-sync` command in `--server` mode behind a TLS-terminating
reverse proxy.

## Prerequisites

- Linux, with [uv](https://docs.astral.sh/uv/) installed.
- A domain name pointed at the server, if you want TLS (recommended for anything
  beyond a private network).

## Install the command

Clone the repository and install its dependencies:

```bash
git clone https://github.com/dimagi/commcare-sync.git
cd commcare-sync
uv sync
```

Then run it with `uv run commcare-sync --server`.

<!-- prettier-ignore-start -->
> [!NOTE]
> `commcare-sync` is not yet published to PyPI, and cannot yet be installed
> as a standalone command: `uv tool install` builds a wheel that is missing
> the application itself, so the installed command does not start. Running
> from a checkout, as above, is the supported path until the packaging work
> lands; `uv tool install commcare-sync` arrives with that work. The systemd
> unit below runs it from the checkout accordingly.
<!-- prettier-ignore-end -->

## Provision the admin account non-interactively

A fresh install has no users, and sends every request to `/setup/` until an
admin account is created there.

<!-- prettier-ignore-start -->
> [!WARNING]
> On a server bound to anything other than loopback, `/setup/` is reachable —
> and world-claimable — by anyone who can reach the port, for as long as no
> admin account exists yet. Set `COMMCARE_SYNC_ADMIN_EMAIL` and
> `COMMCARE_SYNC_ADMIN_PASSWORD` (below) so the admin account exists from the
> moment the service first starts, rather than relying on reaching
> `/setup/` first.
<!-- prettier-ignore-end -->

## Sample systemd unit

Save as `~/.config/systemd/user/commcare-sync.service` (a user unit; adjust
paths for a system-wide unit under `/etc/systemd/system/` and a dedicated
service account instead):

```ini
[Unit]
Description=CommCare Data Pipeline
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/commcare-sync
ExecStart=%h/.local/bin/uv run commcare-sync --server --port 8000
Restart=on-failure
Environment=COMMCARE_SYNC_ADMIN_EMAIL=admin@example.com
Environment=COMMCARE_SYNC_ADMIN_PASSWORD=change-me
Environment=COMMCARE_SYNC_ALLOWED_HOSTS=pipeline.example.com
Environment=COMMCARE_SYNC_BEHIND_PROXY=1

[Install]
WantedBy=default.target
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now commcare-sync
```

`commcare-sync --server` exits non-zero if `--port` is already taken, so a
permanently occupied port makes `Restart=on-failure` retry-loop indefinitely
rather than fail loudly once — check `journalctl --user -u commcare-sync` if the
unit won't settle into a running state.

- `COMMCARE_SYNC_ADMIN_EMAIL` / `COMMCARE_SYNC_ADMIN_PASSWORD` — create the
  admin account at startup instead of via `/setup/`. Both must be set together;
  only takes effect if no user exists yet.
- `COMMCARE_SYNC_ALLOWED_HOSTS` — comma-separated list of hostnames Django will
  serve (Django's `ALLOWED_HOSTS`). Defaults to `*` (any host), which is fine
  behind a reverse proxy that only forwards your own domain, but you can lock it
  down here too.
- `COMMCARE_SYNC_BEHIND_PROXY=1` — tells Django to trust the `X-Forwarded-Proto`
  header from a TLS-terminating reverse proxy, so redirects and cookies use
  `https://` correctly. Only set this if the proxy in front of `commcare-sync`
  actually sets that header and strips any client-supplied one.

`commcare-sync --server` has no built-in TLS; put a reverse proxy in front of it
for anything reachable outside a trusted private network.

## Reverse proxy for TLS

### Caddy

```
pipeline.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy obtains and renews a TLS certificate automatically and sets
`X-Forwarded-Proto` for you.

### nginx

```nginx
server {
    listen 443 ssl;
    server_name pipeline.example.com;

    ssl_certificate     /etc/letsencrypt/live/pipeline.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pipeline.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Either way, set `COMMCARE_SYNC_BEHIND_PROXY=1` in the unit above so Django knows
to trust the forwarded scheme.

## Back up an instance

Everything `commcare-sync` needs — the SQLite database, generated secrets, logs,
and uploaded media — lives under its data directory (default
`~/.local/share/commcare-sync/`, overridable with `--data-dir` or
`COMMCARE_SYNC_DATA_DIR`). Stop the service, copy the whole data directory
somewhere safe, and restart it:

```bash
systemctl --user stop commcare-sync
cp -a ~/.local/share/commcare-sync/ /path/to/backup/
systemctl --user start commcare-sync
```

Restoring is the reverse: stop the service, replace the data directory with the
backed-up copy (including `secrets.json` — without it, encrypted credentials in
the restored database can't be decrypted), and start it again.

## Next steps

- [Download CommCare Data Pipeline logs](download-pipeline-logs.md) — the
  launcher writes its own log to `<data-dir>/logs/launcher.log`, alongside the
  shared `commcare_export.log`.
