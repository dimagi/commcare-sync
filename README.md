CommCare Data Pipeline
======================

> [!WARNING]
> **The documentation is out of date.** The guides under [docs/](docs/)
> and the linked production documentation describe an earlier version of
> Data Pipeline. A full refresh is planned. Until then, use
> [Getting Started](#getting-started) below, and treat the rest of the
> documentation as legacy.

CommCare Data Pipeline continuously exports CommCare data into your own
databases and BI platforms.

It is a self-hosted, standalone web application designed to manage a
CommCare data warehouse over the command-line
[CommCare Data Export Tool](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET).

This turnkey solution allows you to export data from CommCare and store
it in a local or cloud-based database, including MySQL, PostgreSQL,
Microsoft SQL Server, Amazon RDS, GCP Cloud SQL, and Azure SQL Database.

With CommCare Data Pipeline, you can utilise these key features:

- **Automated Configuration:** Import a Data Export Tool (DET)
  configuration directly from CommCare.

- **Seamless Integration:** Connect CommCare Data Pipeline to your
  CommCare project space(s) and database(s).

- **Scheduled Data Exports:** Automate data transfers from CommCare to
  your database on a defined schedule.

- **Data Forwarding:** Forward data automatically from your database to
  a RESTful JSON API on a scheduled basis.

- **Export Monitoring:** Track and manage data export activities through
  CommCare Data Pipeline’s built-in log feature.

See [the documentation](docs/index.md) for details on installing a
development environment and setting up a test data pipeline.

See the
[**commcare-sync-ansible** documentation](https://commcare-sync-ansible.readthedocs.io/en/latest/)
for details on installing and managing a production environment.


Getting Started
---------------

These steps run Data Pipeline in a Linux terminal. You need
[uv](https://docs.astral.sh/uv/getting-started/installation/) and Git.
uv installs a suitable version of Python if you don't have one.

1. Clone the repository and install the dependencies:

   ```shell
   git clone https://github.com/dimagi/commcare-sync.git
   cd commcare-sync
   uv sync
   ```

   To export to a PostgreSQL, MySQL or SQL Server database, add its
   driver with `uv sync --extra postgres`, `--extra mysql` or
   `--extra odbc`.

2. Create `commcare_sync/settings_local.py`, which Git ignores, with a
   secret key and an encryption key:

   ```shell
   cat > commcare_sync/settings_local.py <<EOF
   SECRET_KEY = '$(uv run python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')'
   FERNET_KEYS = ['$(./fernet-gen)']
   DEBUG = True
   EOF
   ```

   `FERNET_KEYS` encrypts the credentials that Data Pipeline stores. If
   you lose it, they can't be decrypted.

3. Create the database and an admin user. Data Pipeline stores its own
   data in SQLite, in `db.sqlite3`.

   ```shell
   uv run python manage.py migrate
   uv run python manage.py createsuperuser
   ```

4. Start the web server:

   ```shell
   uv run python manage.py runserver
   ```

   Open <http://localhost:8000/> and log in with the email address and
   password you just chose.

5. In a second terminal, start the task cluster. It performs exports,
   forwarding and refreshes, both scheduled and manual.

   ```shell
   uv run python manage.py qcluster
   ```


Running the Launcher
--------------------

The launcher runs the web server and supervises the task cluster, so
there is one command to start and nothing to configure: it needs no
`settings_local.py`.

```shell
uv run commcare-sync
```

It listens on every address on port 8000; open <http://localhost:8000/>.
On first run, open the setup link that the launcher prints instead, to
create the admin user. Pass `--port` to listen elsewhere, and `--bind`
to listen on one address only. Pass `--desktop` to run for one user on
this computer: it listens on a free port on `127.0.0.1` and shows the
app in a window on Windows and macOS, or in your browser on Linux.
Closing the window stops the app, and asks first while a run is in
progress; the run is marked interrupted and runs again on the next
start.

The launcher keeps the database, encryption keys, logs and uploaded
files in a data directory, separate from this checkout's `db.sqlite3`:
`~/.local/share/commcare-sync` on Linux,
`~/Library/Application Support/commcare-sync` on macOS, and
`%LOCALAPPDATA%\commcare-sync` on Windows. Pass `--data-dir` or set
`COMMCARE_SYNC_DATA_DIR` to use another. The launcher writes to
`logs/launcher.log` there, and the app to `logs/app.log`. Management
commands run against the same data directory when
`COMMCARE_SYNC_DATA_DIR` is set. To stop the launcher without a
terminal, create a file named `stop` in the data directory.

The setup page only works from a browser running on the server, opened
at the link the launcher printed, so that nobody else on the network,
or on the server, can claim the admin account. The link is also in
`logs/launcher.log`, and changes on every start. Requests that carry a
forwarding header, or that ask for any other host name, are refused. A
plain TCP forwarder (`ssh -R`, `socat`) adds no header, so do not expose
the port through one before the admin user exists. To create the admin
user without the page, set `COMMCARE_SYNC_ADMIN_EMAIL` and
`COMMCARE_SYNC_ADMIN_PASSWORD` before the first run; the password must
pass the same checks as the setup form. Both variables are forgotten
once read, so they can be dropped after that run.

Behind an HTTPS reverse proxy, set `COMMCARE_SYNC_BEHIND_PROXY=1` so
that the server trusts the proxy's `X-Forwarded-Proto` header, and pass
`--bind 127.0.0.1` so that the proxy is the only way in. The setup
page is then disabled and the admin user must come from the
environment variables above. In server mode the launcher answers to
any host name by default, which is safe here because password-reset
links are built from the configured site domain, not from the request;
set `COMMCARE_SYNC_ALLOWED_HOSTS` to a comma-separated list to restrict
it anyway.

Any other Django setting can be overridden in a `settings.py` in the
data directory, which is run as code and so must be yours and not
world-writable; the application database location cannot be changed.
Behind a proxy that serves HTTPS only, set `SESSION_COOKIE_SECURE = True`
and `CSRF_COOKIE_SECURE = True` there, so that a browser never sends
the cookies over plain HTTP, and have the proxy send the HSTS header.
The launcher leaves these alone because a proxy may equally serve plain
HTTP, and secure cookies would then never come back.
