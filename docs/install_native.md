Installing natively
-------------------

You can also install CommCare Data Pipeline directly on your operating
system using the instructions below.

### Prerequisites

- PostgreSQL (or other SQL database, but you'll have to edit the
  settings if not Postgres)

- Redis

### Install the source code

Clone this repository:
```shell
git clone https://github.com/dimagi/commcare-sync.git
```

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

Uncomment `SECRET_KEY` and `FERNET_KEYS` in `commcare_sync/settings.py`
and create secure values for them:

To generate a value for `SECRET_KEY` you can use
```shell
openssl rand -base64 48
```

To generate a Fernet key, use
```shell
./fernet-gen
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

### Testing with Playwright

On Ubuntu, `uv sync --dev` (above) will automatically install Playwright
and the host operating system packages it needs.

If the host OS packages are not installed automatically, use an LLM to
find your operating system's equivalent of the following packages, and
install them:

* libicu74
* libxml2
* libgstreamer-plugins-bad1.0-0
* libflite1
* libmanette-0.2-0
* libwoff1
* gstreamer1.0-libav

By default Playwright will be installed with all browsers. To install
with a specific browser only (Chromium, for example):

```shell
uv run playwright install chromium
```

To (re)install with all browsers:

```shell
uv run playwright install
```

Run tests in headed mode, to see the browser:

```shell
uv run pytest apps/example/tests/test_example.py --headed
```

Run tests in slow motion, for debugging:

```shell
uv run pytest apps/example/tests/test_example.py --headed --slowmo 1000
```

Run with Playwright Inspector, the step-through debugger:

```shell
PWDEBUG=1 uv run pytest apps/example/tests/test_example.py
```
