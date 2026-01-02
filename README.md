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

See [the documentation](docs/index.md) for details on installing a
development environment and setting up a test data pipeline.

See the
[**commcare-sync-ansible** documentation](https://commcare-sync-ansible.readthedocs.io/en/latest/)
for details on installing and managing a production environment.
