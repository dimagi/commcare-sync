Installing a development environment with Docker
------------------------------------------------

The easiest way to get up and running is with
[Docker](https://www.docker.com/).

<details>
<summary>Running Windows? Click to expand setup instructions</summary>

Install Ubuntu on Windows Subsystem for Linux:

1. Open PowerShell in **administrator mode** by right-clicking and
   selecting "Run as administrator".

2. Enter the following command:
   ```powershell
   wsl --install
   ```
   You will need to reboot your machine during the installation process.

3. Once installation is complete, open Ubuntu using the Start menu.

4. The first time you open Ubuntu, you will be asked to create a
   username and password. (When you enter a password, nothing will
   appear on the screen.) In the future you will automatically be signed
   in as this user. It will be a system administrator with the ability
   to run commands with `sudo` ("superuser do").

[Learn more here](https://learn.microsoft.com/en-gb/windows/wsl/setup/environment).

</details>

1. Install requirements:
   1. [Docker](https://www.docker.com/get-started)
   2. [Docker Compose](https://docs.docker.com/compose/install/)
   3. [uv](https://docs.astral.sh/uv/getting-started/installation/).

2. Clone this repository:
   ```shell
   git clone https://github.com/dimagi/commcare-sync.git
   ```

3. Create `commcare_sync/local_settings.py` and add `SECRET_KEY` and
   `FERNET_KEYS` values to it:

   See the comment in `commcare_sync/settings.py` regarding `SECRET_KEY`
   and `FERNET_KEYS`.

   To generate a value for `SECRET_KEY` you can use
   ```shell
   openssl rand -base64 48
   ```

   To generate a Fernet key, use
   ```shell
   ./fernet-gen
   ```

   Using your preferred editor, create `commcare_sync/local_settings.py`
   and add the variables as they appear in the comment in
   `commcare_sync/settings.py`.

4. Initialize the database and start the server:
   ```shell
   make init
   ```

   This will spin up a database, web worker, celery worker, and Redis
   broker and run your migrations.

5. Create a superuser:

   ```shell
   docker-compose exec web uv run manage.py createsuperuser
   ```

   Use the email address as the username value too.

CommCare Data Pipeline is ready. Go to http://localhost:8000/ to log in.


Stopping
--------

To stop CommCare Data Pipeline on Docker, run:
```shell
make stop
```


Starting
--------

To start CommCare Data Pipeline again, run:
```shell
make start
```


Updating
--------

To update CommCare Data Pipeline code:
```shell
make stop  # If CommCare Data Pipeline is running
git pull
make init
```


Using the Makefile
------------------

You can run `make` to see other helper functions. View `Makefile` to see
what commands the functions run.
