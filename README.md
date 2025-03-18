# Note on usage

Warning: The CommCare Sync project is **not actively maintained**. Interested parties are recommended to review the [CommCare Data Export Tool](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET) as an alternative which is actively maintained. CommCare Sync implementers should expect to need to perform their own modernization and maintenance. 

CommCare Sync is a community-of-practice open source project, and not an officially supported tool. It's free and available as an example and for use, and contribututions are welcome from the community, but there are currently no plans to update or modernize the project.

# CommCare Sync

CommCare Sync simplifies the setup and management of your CommCare data pipeline. It is a self-hosted, standalone web application designed to manage a CommCare “data warehouse” over the command-line [CommCare Data Export Tool](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET?atl_f=PAGETREE). This turnkey solution allows you to export data from CommCare and store it in a local or cloud-based database, including MySQL, PostgreSQL, Amazon RDS, GCP Cloud SQL, and Azure SQL Database. With CommCare Sync, you can utilise these key features: 
- **Automated Configuration:** Generate a Data Export Tool (DET) configuration file directly from CommCare.
- **Seamless Integration:** Connect CommCare Sync to your CommCare project space(s) and database(s).
- **Scheduled Data Syncs:** Upload a DET configuration file to automate data transfers from CommCare to your database on a defined schedule.
- **Sync Monitoring:** Track and manage data sync activities through CommCare Sync’s built-in log feature.

**This documentation shows you how to set up a self-hosted version of CommCare Sync using the source code.**  For help installing and managing production environments, you can follow the [documentation](https://commcare-sync-ansible.readthedocs.io/en/latest/) of the commcare-sync ansible repository.

## Production Setup

### Configuration Steps

To configure CommCare Sync:

1. In CommCare HQ Data page, create a form or case export 
2. Download the DET config file
3. Open your Excel DET config file to see the fields from your export with the option of mapping specific data types. If you aren't transforming your data, there's no step needed here.
4. Open CommCare Sync, create a new account (instructions below)
5. Add a project by pasting your CommCare project space name
6. Add your database via the Admin Site (can be any available database)
7. Add an export from your new project, and add your database and your config file you downloaded in step 2
8. Run export. This applies the configuration file to do an initial sync of all the data from your CommCare project space. 
9. View the log to see more info - like to confirm how much data was pulled in
10. Connect your BI tool of choice, and start exploring the data

### Note for projects syncing data from multiple CommCare project spaces: 

The process described above is for connecting a single CommCare project space. If you are connecting data from multiple CommCare project spaces, you need to add each project space as a Project in CommCare Sync (step 5), and repeat the process of downloading each DET config file per project space (step 2), to then each be uploaded to CommCare Sync (steps 7 & 8).  (IMPORTANT:  there is a new feature release that will allow applying the same DET config file to multiple project spaces in the CommCare sync tool).

### Download your DET config file from CommCare

- Download or create a [Data Export Tool](https://dimagi.atlassian.net/wiki/x/8CvKfw) config file.
- The easiest way to create these is to start with a normal export configuration on HQ and have it generated. See here for more details: [CommCare Data Export Tool (DET) | Creating an Excel Query File in CommCare HQ](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET#Creating-an-Excel-Query-File-in-CommCare-HQ)
- Edit the DET file using the “best practices” below

### Create a CommCare Sync account
Ask a site admin to create an account for you and share credentials, then change your password.

### Sync your data

To sync data, follow the following steps:

1. If you haven’t already, add the CommCare project space in the “CommCare Setup” tab.
2. If you haven’t already, add a CommCare account that has access to the project space.
3. Note: If you have a privileged account, it's recommnded that you create a service account in the target project space instead with minimal permissions and use that for data syncing. 
4. Add the export from the “Exports” tab.
5. On the export details page, click “run”.
6. When the run completes, view the logs to confirm it ran successfully.

Data will be updated for all exports on a schedule (currently every 12 hours, managed by a system admin).

### Data Export Tool Best Practices

Some recommendations for modifying the DET config files downloaded from HQ:

1. Double check the name of the sheet (tab) in your DET config workbook to be something specific to your project / case type. The tab's name, not the .xlsx file name, will be used as the table name in SQL. The default of  “Cases” or “Forms” should not be used, but instead changed to e.g. “covid_19_index_cases”
2. Add a “str2date” mapping to any date properties and fields. This will make it easier to use them in various BI tools.
3. There is a subtle difference between the 'Extra Arguments' field in a CommCare Sync Export and a CommCare Data Export Tool parameter. If an argument in CommCare Sync takes multiple parameters ('since' and 'until,' for example) it must be formatted like: --until=2020-09-30

### Adding Databases

Databases can be added by site admins by using the "databases" link in CommCare Sync sidebar navigation. The database may need to also be separately created by a system admin on the server.

### Administration

System administration is documented in our [production environment documentation](https://commcare-sync-ansible.readthedocs.io/en/latest/system-administration.html).

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
