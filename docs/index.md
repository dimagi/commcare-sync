# CommCare Data Pipeline

CommCare Data Pipeline copies your CommCare data into a database that you own,
on a schedule, so that you can report on it with the tools you already use. It
runs on your own computer as a desktop app, or on a shared server for a team.

## How the pieces fit

- A **project** names a CommCare HQ project space, and an **account** holds the
  login used to read it.
- A **database** is where the data goes: PostgreSQL, MySQL or SQL Server.
- An **export** copies one saved CommCare HQ export into the database, and keeps
  it up to date.
- A **refresh** rebuilds summary views in the database after new data arrives.
- A **forwarder** sends the result of a query to another system, such as DHIS2
  or a CommCare HQ lookup table.

## Getting started

1. [Install CommCare Data Pipeline](install.md)
2. [Add a CommCare project](add-commcare-project.md)
3. [Add a CommCare account](add-commcare-account.md)
4. [Add a database](add-database.md)
5. [Set up an export](set-up-export.md)

## Going further

- [Export from several projects at once](multi-project-export.md)
- [Schedules](schedules.md)
- [Refresh materialized views](refresh-materialized-views.md)
- [Forward data](forward-data.md)
- [Monitor runs](monitor-runs.md)

## Administration

- [Manage users](manage-users.md)
- [Run on a server](server.md)
- [Troubleshooting](troubleshooting.md)
- [Pilot builds](pilot_guide.md)

## For developers

The [README](../README.md) covers setting up a development environment, and
[CONTRIBUTING](../CONTRIBUTING.md) the coding conventions.
