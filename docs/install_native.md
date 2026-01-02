Installing natively
-------------------

You can also install CommCare Data Pipeline directly on your operating
system using the instructions below.

### Prerequisites

- PostgreSQL (or other SQL database, but you'll have to edit the
  settings if not Postgres)

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

### Running the server

```shell
./manage.py runserver
```

### Building the front-end

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

Celery is used to run background tasks and scheduled tasks like export
runs. To run it you can use:

```shell
celery -A commcare_sync worker -l info
```

Or to also include periodic tasks to run all exports on a schedule:

```shell
celery -A commcare_sync worker -l info -B
```

### Running tests

To run tests:

```shell
pytest
```
