Configuring CommCare Data Pipeline
----------------------------------

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

8. Run export. This applies the configuration file to do an initial
   export of all the data from your CommCare project space.

9. View the log to see more info - like to confirm how much data was
   pulled in

10. Connect your BI tool of choice, and start exploring the data

### Note for projects exporting data from multiple CommCare project spaces: 

The process described above is for connecting a single CommCare project
space. If you are connecting data from multiple CommCare project
spaces, you need to add each project space as a Project in CommCare
Data Export (step 5). Repeat the process of downloading each DET
config file per project space (step 2). Then upload them to CommCare
Data Pipeline (steps 7 & 8).

### Download your DET config file from CommCare

- Download or create a
  [Data Export Tool](https://dimagi.atlassian.net/wiki/x/8CvKfw)
  config file.

- The easiest way to create one is to start with a normal export
  configuration on HQ and have it generated. See here for more details:
  [CommCare Data Export Tool (DET) | Creating an Excel Query File in CommCare HQ](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET#Creating-an-Excel-Query-File-in-CommCare-HQ)

- Edit the DET file using the “best practices” below

### Create a CommCare Data Pipeline account

Ask a site admin to create an account for you and share credentials,
then change your password.

### Optional: Set up CommCare OAuth

CommCare OAuth integration enables easier configuration by allowing you to
browse your available domains, case types, and export configurations directly
from CommCare. See [OAuth Setup](oauth_setup.md) for instructions.

**Note:** OAuth is for configuration assistance only. You still need API keys
for running production exports.

### Export your data

To export data, follow the following steps:

1. If you haven’t already, add the CommCare project space in
   the “CommCare Setup” tab.

2. If you haven’t already, add a CommCare account that has access to the
   project space.

3. Note: If you have a privileged account, it's recommended that you
   create a service account in the target project space instead with
   minimal permissions and use that for data exporting.

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
   not the .xlsx filename, will be used as the table name in SQL. The
   default of “Cases” or “Forms” should not be used, but instead
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
