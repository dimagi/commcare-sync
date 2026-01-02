Installing a development environment with Docker
------------------------------------------------

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

Go to http://localhost:8000/ to view the app.


### Using the Makefile

You can run `make` to see other helper functions, and you can view the
source of the file in case you need to run any specific commands.

For example, you can run management commands in containers using the
same method used in the `Makefile`. e.g.

```shell
docker-compose exec web uv run manage.py createsuperuser
```
