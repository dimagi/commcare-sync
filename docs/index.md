# CommCare Data Pipeline documentation

CommCare Data Pipeline lets an organization export data from
[CommCare HQ](https://github.com/dimagi/commcare-hq/) into databases it owns,
schedule transformations and aggregations, and forward results to external
systems.

## User guides

- [Add a CommCare Project](users/add-commcare-project.md)
- [Add a CommCare Account](users/add-commcare-account.md)
- [Add a database](users/add-database.md)
- [Set up an export](users/set-up-export.md)
- [Schedule a materialized view refresh](users/schedule-materialized-view-refresh.md)
- [Forward data to DHIS2](users/forward-to-dhis2.md)
- [Forward data to a CommCare fixture](users/forward-to-commcare-fixture.md)
- [Understanding the statistics](users/understanding-statistics.md)
- [Checking the logs for a run](users/checking-run-logs.md)

## Admin guides

- [Add a new user](admin/add-user.md)
- [Reset a password](admin/reset-password.md)
- [Delete a user](admin/delete-user.md)
- [Add a CommCare HQ server](admin/add-commcare-server.md)
- [Download CommCare Data Pipeline logs](admin/download-pipeline-logs.md)

## Development

See [DEV_SETUP.md](../DEV_SETUP.md) for setting up a local development
environment.

## Production

For installing and deploying a production environment, see the Ansible
documentation at
<https://commcare-sync-ansible.readthedocs.io/en/latest/system-administration.html>.
