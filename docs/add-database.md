# Add a database

A database is where your exported data goes. Exports write to it, refreshes
rebuild views in it, and forwarders read from it. You need an administrator
account in CommCare Data Pipeline to add one.

## Before you start

- A PostgreSQL, MySQL or SQL Server database that already exists. The app does
  not create the database itself, only the tables inside it.
- A database user who can create tables in it, and that user's password.
- The address and port of the database server. Your database administrator or
  hosting provider has these.
- For SQL Server, Microsoft's ODBC Driver for SQL Server installed on the
  computer that runs the app.

## Steps

1. In the sidebar, under **Export Management**, click **Databases**, then **New
   Database Connection**.
2. In **Name**, type a name that tells you which database this is, for example
   `Pipeline (PostgreSQL)`.
3. In **Connection String**, type the address of the database in this form,
   replacing each part with your own:

   | Database   | Connection string                                                                      |
   | ---------- | -------------------------------------------------------------------------------------- |
   | PostgreSQL | `postgresql://user:password@host:5432/database`                                        |
   | MySQL      | `mysql+pymysql://user:password@host:3306/database`                                     |
   | SQL Server | `mssql+pyodbc://user:password@host:1433/database?driver=ODBC+Driver+18+for+SQL+Server` |

   If the password contains `@`, `:`, `/` or `#`, write those characters as
   `%40`, `%3A`, `%2F` and `%23`.

4. Click **Create**.

![The Create Database form, with Name and Connection String](images/add-database.png)

<!-- prettier-ignore-start -->
> [!NOTE]
> The connection is not tested when you save it. The first export that uses it
> shows an error in its log if the address, the user or the password is wrong.
> See [Troubleshooting](troubleshooting.md).
<!-- prettier-ignore-end -->

The connection string contains the password. It is stored encrypted, and is not
shown again when you edit the database. Leave the field blank when editing to
keep the one you have.

## Next

- [Set up an export](set-up-export.md)
