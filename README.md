# CommCare Sync

A Management Interface for the CommCare Data Export Tool.

Some additional context on this project can be [found here](https://docs.google.com/document/d/1r8ZQAjCGbxX8pXWtIq0ODJOpqqI27YqPDN4vuR_CLGw/edit) (Dimagi Internal).

For deploying this tool to a production server, see [commcare-sync-ansible](https://github.com/dimagi/commcare-sync-ansible)

## Developer Setup - Docker

The easiest way to get up and running is with [Docker](https://www.docker.com/).

Just [install Docker](https://www.docker.com/get-started) and
[Docker Compose](https://docs.docker.com/compose/install/)
and then run:
 
```
make init
```

This will spin up a database, web worker, celery worker, and Redis broker and run your migrations.

You go to [localhost:8000](http://localhost:8000/) to view the app.

### Using the Makefile

You can run `make` to see other helper functions, and you can view the source
of the file in case you need to run any specific commands.

For example, you can run management commands in containers using the same method 
used in the `Makefile`. E.g.

```
docker-compose exec web python manage.py createsuperuser
```

## Developer Setup - Native

You can also install/run the app directly on your OS using the instructions below.

### Prerequisites
- Python 3.8
    On Ubuntu:
    ```bash
    sudo apt-get install python3.8 python3.8-dev
    ```
- Postgres (or other SQL DB, but you'll have to edit the settings if not postgres)
- Redis

Setup a virtualenv and install requirements:

```bash
mkvirtualenv --no-site-packages commcare_sync -p $(which python3.8)
pip install -r requirements.txt
```

Create a database:

```bash
psql -U <dbuser> -h localhost -p 5432
CREATE DATABASE commcare_sync;
\q
./manage.py migrate
```

### Running server

```bash
./manage.py runserver
```

### Building front-end

To build JavaScript and CSS files, first install npm packages:

```bash
npm install
```

Then to build (and watch for changes locally) just run:

```bash
npm run dev-watch
```

To build the files for production run:

```bash
npm run build
```

### Running Celery

Celery is used to run background tasks, including all the commcare-export runs as well as 
the scheduled tasks. To run it you can use:

```bash
celery -A commcare_sync worker -l info
```

Or to also include periodic tasks to run all exports on a schedule:

```bash
celery -A commcare_sync worker -l info -B
```

### Running Tests

To run tests:

```bash
./manage.py test
```

## Deployment

To set up a production server, see [commcare-sync-ansible](https://github.com/dimagi/commcare-sync-ansible)

### Deploying with Fabric

For incremental deploys you can also use `fabric`. First install it:

```bash
pip install -r requirements/dev-requirements.txt
```

Then:

```bash
fab -H commcare-sync-demo2.dimagi.com -f deploy/environments/demo.yml deploy
```

You'll have to set up authentication using something like [this guide](https://stackoverflow.com/a/5071823/8207).

Here's an example `/.ssh/config` entry:

```
Host commcare-sync-demo2.dimagi.com
  User ubuntu
  HostName commcare-sync-demo2.dimagi.com
  IdentityFile ~/.ssh/Covid.pem
```
