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

**This documentation shows you how to set up a self-hosted version of
CommCare Data Pipeline using the source code.**  For help installing and managing
production environments, you can follow the
[documentation](https://commcare-sync-ansible.readthedocs.io/en/latest/)
of the commcare-sync ansible repository.


Production Setup
----------------

### Configuration Steps

To configure CommCare Data Pipeline:

1. In CommCare HQ Data page, create a form or case export 

2. Download the DET config file

3. Open your Excel DET config file to see the fields from your export
   with the option of mapping specific data types. If you aren't
   transforming your data, there's no step needed here.

4. Open CommCare Data Pipeline, create a new account (instructions below)

5. Add a project by pasting your CommCare project space name

6. Add your database via the Admin Site (can be any available database)

7. Add an export from your new project, and add your database and your
   config file you downloaded in step 2

8. Run export. This applies the configuration file to do an initial sync
   of all the data from your CommCare project space.

9. View the log to see more info - like to confirm how much data was
   pulled in

10. Connect your BI tool of choice, and start exploring the data

### Note for projects syncing data from multiple CommCare project spaces: 

The process described above is for connecting a single CommCare project
space. If you are connecting data from multiple CommCare project
spaces, you need to add each project space as a Project in CommCare
Sync (step 5), and repeat the process of downloading each DET config
file per project space (step 2), to then each be uploaded to CommCare
Sync (steps 7 & 8).  (IMPORTANT:  there is a new feature release that
will allow applying the same DET config file to multiple project spaces
in the CommCare sync tool).

### Download your DET config file from CommCare

- Download or create a
  [Data Export Tool](https://dimagi.atlassian.net/wiki/x/8CvKfw) config
  file.

- The easiest way to create these is to start with a normal export
  configuration on HQ and have it generated. See here for more details:
  [CommCare Data Export Tool (DET) | Creating an Excel Query File in CommCare HQ](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET#Creating-an-Excel-Query-File-in-CommCare-HQ)

- Edit the DET file using the “best practices” below

### Create a CommCare Data Pipeline account

Ask a site admin to create an account for you and share credentials,
then change your password.

### Sync your data

To sync data, follow the following steps:

1. If you haven’t already, add the CommCare project space in
   the “CommCare Setup” tab.

2. If you haven’t already, add a CommCare account that has access to the
   project space.

3. Note: If you have a privileged account, it's recommnded that you
   create a service account in the target project space instead with
   minimal permissions and use that for data syncing.

4. Add the export from the “Exports” tab.

5. On the export details page, click “run”.

6. When the run completes, view the logs to confirm it ran
   successfully.

Data will be updated for all exports on a schedule (currently every 12
hours, managed by a system admin).

### Data Export Tool Best Practices

Some recommendations for modifying the DET config files downloaded from HQ:

1. Double check the name of the sheet (tab) in your DET config workbook
   to be something specific to your project / case type. The tab's name,
   not the .xlsx file name, will be used as the table name in SQL. The
   default of  “Cases” or “Forms” should not be used, but instead
   changed to e.g. “covid_19_index_cases”

2. Add a “str2date” mapping to any date properties and fields. This will
   make it easier to use them in various BI tools.

3. There is a subtle difference between the 'Extra Arguments' field in a
   CommCare Data Pipeline Export and a CommCare Data Export Tool
   parameter. If an argument in CommCare Data Pipeline takes multiple
   parameters ('since' and 'until', for example) it must be formatted
   like: --until=2020-09-30

### Adding Databases

Databases can be added by site admins by using the "databases" link in
CommCare Data Pipeline sidebar navigation. The database may need to also
be separately created by a system admin on the server.

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
