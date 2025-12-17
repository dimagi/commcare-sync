CommCare Data Pipeline
======================

CommCare Data Pipeline simplifies the setup and management of your
CommCare data pipeline.

It is a self-hosted, standalone web application designed to manage a
CommCare “data warehouse” over the command-line
[CommCare Data Export Tool](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET).

This turnkey solution allows you to export data from CommCare and store
it in a local or cloud-based database, including MySQL, PostgreSQL,
Amazon RDS, GCP Cloud SQL, and Azure SQL Database. With CommCare Data
Pipeline, you can utilise these key features:

- **Automated Configuration:** Generate a Data Export Tool
  (DET) configuration file directly from CommCare.

- **Seamless Integration:** Connect CommCare Data Pipeline to your
  CommCare project space(s) and database(s).

- **Scheduled Data Exports:** Upload a DET configuration file to
  automate data transfers from CommCare to your database on a defined
  schedule.

- **Export Monitoring:** Track and manage data export activities through
  CommCare Data Pipeline’s built-in log feature.

See [the documentation](docs/index.md) for details on configuring
CommCare Data Pipeline, how to install and contribute.

**This documentation shows you how to set up a self-hosted version of
CommCare Data Pipeline using the source code.**  For help installing and managing
production environments, you can follow the
[documentation](https://commcare-sync-ansible.readthedocs.io/en/latest/)
of the commcare-sync ansible repository.


### Administration

System administration is documented in our
[production environment documentation](https://commcare-sync-ansible.readthedocs.io/en/latest/system-administration.html).


Developer Setup - Docker
------------------------

The easiest way to get up and running is with
[Docker](https://www.docker.com/).

Just [install Docker](https://www.docker.com/get-started) and
[Docker Compose](https://docs.docker.com/compose/install/) and then
run:
 
```shell
make init
```

This will spin up a database, web worker, celery worker, and Redis
broker and run your migrations.

You go to [localhost:8000](http://localhost:8000/) to view the app.

### Using the Makefile

You can run `make` to see other helper functions, and you can view the
source of the file in case you need to run any specific commands.

For example, you can run management commands in containers using the
same method used in the `Makefile`. e.g.

```shell
docker-compose exec web uv run manage.py createsuperuser
```


Developer Setup - Native
------------------------

You can also install/run the app directly on your OS using the
instructions below.

### Prerequisites

- PostgreSQL (or other SQL DB, but you'll have to edit the settings if
  not Postgres)

- Redis

Install uv:
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Create a virtual environment and install dependencies:
```shell
uv sync --dev
```

To activate the virtual environment:
```shell
source .venv/bin/activate
```

Create a database:

```shell
psql -U <dbuser> -h localhost -p 5432
CREATE DATABASE commcare_sync;
\q
./manage.py migrate
```

### Running server

```shell
./manage.py runserver
```

### Building front-end

To build JavaScript and CSS files, first install npm packages:

```shell
npm install
```

Then to build (and watch for changes locally) just run:

```shell
npm run dev-watch
```

To build the files for production run:

```shell
npm run build
```

### Running Celery

Celery is used to run background tasks, including all the
commcare-export runs as well as the scheduled tasks. To run it you can
use:

```shell
celery -A commcare_sync worker -l info
```

Or to also include periodic tasks to run all exports on a schedule:

```shell
celery -A commcare_sync worker -l info -B
```

### Running Tests

To run tests:

```shell
./manage.py test
```


Deployment
----------

To set up a production server, see
[commcare-sync-ansible](https://github.com/dimagi/commcare-sync-ansible)
