# Add a database

Register a database where CommCare Data Pipeline will write exported data.
Exports, refreshes, and forwarders all attach to one of these connections.

## Prerequisites

- A database that already exists on the target server. CommCare Data Pipeline
  does not create databases for you — it only connects to one you've already set
  up.
- A database user with permission to read, write, and create tables in that
  database.
- Network access from the CommCare Data Pipeline host to the database server, on
  the database's listening port.

<!-- prettier-ignore-start -->
> [!TIP]
> If you need to create the target database, connect with `psql` (or your
> SQL client of choice) and run:
>
> ```sql
> CREATE DATABASE my_pipeline_database;
> ```
<!-- prettier-ignore-end -->

The pipeline talks to the target database through SQLAlchemy, so any engine
SQLAlchemy supports — PostgreSQL, MySQL, SQL Server, and others — can be used,
as long as the matching driver is installed on the pipeline host. PostgreSQL is
the standard choice.

## Steps

1. In the sidebar, go to **Export Management → Databases**.

2. Click **+ New Database Connection** in the top right of the database
   connections list.

   ![The Create Database form, with Name and Connection String fields.](../images/add-database.png)

3. On the **Create Database** page, fill in the form:
   - **Name** — a short label for this connection, shown wherever you pick a
     database (for example `Docs walkthrough`).
   - **Connection String** — a SQLAlchemy URL pointing at the target database.
     For a PostgreSQL database running on the pipeline's dev stack, that looks
     like:

     ```
     postgresql://postgres:postgres@localhost:5433/ccsync_docs_walkthrough
     ```

     The general shape is `dialect://user:password@host:port/database_name`. Use
     `mysql+pymysql://…`, `mssql+pyodbc://…`, etc. for other engines.

4. Click **Create**. You return to the database connections list and the new
   connection appears in the table.

<!-- prettier-ignore-start -->
> [!NOTE]
> Both fields are required, and the form does not include a "test
> connection" button — the first time the pipeline really exercises the
> connection is when an export runs against it. If the host, port, user,
> password, or database name is wrong, that export run fails with the
> driver's error message in the run log.
<!-- prettier-ignore-end -->

<!-- prettier-ignore-start -->
> [!NOTE]
> If you're running the pipeline in Docker alongside the database
> container, the host the pipeline needs to reach is not always the host
> you'd use from your laptop. The connection string should use the
> database container's service name (for example `db`) rather than
> `localhost`, and the in-container port (typically `5432`) rather than
> any host-port mapping.
<!-- prettier-ignore-end -->

<!-- prettier-ignore-start -->
> [!WARNING]
> Connection strings contain the database password. They're stored
> encrypted, and the form does not redisplay the value when you edit a
> connection — but treat the value like any other secret while you're
> handling it.
<!-- prettier-ignore-end -->

## Next steps

- [Set up an export](set-up-export.md) — point an export at this database to
  start landing CommCare data in it.
