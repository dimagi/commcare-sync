# CommCare Sync

A Management Interface for the CommCare Data Export Tool.

Some additional context on this project can be [found here](https://docs.google.com/document/d/1r8ZQAjCGbxX8pXWtIq0ODJOpqqI27YqPDN4vuR_CLGw/edit) (Dimagi Internal).

For deploying this tool to a production server, see [commcare-sync-ansible](https://github.com/dimagi/commcare-sync-ansible)

## Developer Setup

### Prerequisites
- Python 3.8
    On Ubuntu:
    ```bash
    sudo apt-get install python3.8 python3.8-dev
    ```
- Postgres

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
fab -H commcare-sync-demo.dimagi.com -f deploy/environments/demo.yml deploy
```

You'll have to set up authentication using something like [this guide](https://stackoverflow.com/a/5071823/8207).

Here's an example `/.ssh/config` entry:

```
Host commcare-sync-demo.dimagi.com
  User ubuntu
  HostName commcare-sync-demo.dimagi.com
  IdentityFile ~/.ssh/Covid.pem
```
