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
