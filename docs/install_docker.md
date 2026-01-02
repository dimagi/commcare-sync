Installing a development environment with Docker
------------------------------------------------

The easiest way to get up and running is with
[Docker](https://www.docker.com/).

1. [Install Docker](https://www.docker.com/get-started),
   [Docker Compose](https://docs.docker.com/compose/install/) and
   [uv](https://docs.astral.sh/uv/getting-started/installation/).

2. Clone this repository:
   ```shell
   git clone https://github.com/dimagi/commcare-sync.git
   ```

3. Uncomment `SECRET_KEY` and `FERNET_KEYS` in `commcare_sync/settings.py`
   and create secure values for them:

   To generate a value for `SECRET_KEY` you can use
   ```shell
   openssl rand -base64 48
   ```

   To generate a Fernet key, use
   ```shell
   ./fernet-gen
   ```

4. Run
   ```shell
   make init
   ```

   This will spin up a database, web worker, celery worker, and Redis
   broker and run your migrations.

Go to http://localhost:8000/ to view the app.


### Using the Makefile

You can run `make` to see other helper functions, and you can view the
source of the file in case you need to run any specific commands.

For example, you can run management commands in containers using the
same method used in the `Makefile`. e.g.

```shell
docker-compose exec web uv run manage.py createsuperuser
```
