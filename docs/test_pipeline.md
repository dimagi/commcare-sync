Setting up a test data pipeline
-------------------------------

To verify a data pipeline, working from data collection to report
rendering, we should start by determining what data we want to appear in
the report. And for that, we should dive into DHIS2.

### Credentials for DHIS2

Navigate to https://im.dhis2.org/public/instances and select a stable
branch. You will be taken to a login page. Log in with username "admin"
and password "district".

### Identifying indicators in DHIS2 to collect data for in CommCare

You will be presented with an Antenatal Care dashboard. To make testing
easier, we want a graph that shows data for last month. Click the
"Dashboards" button in the top left, and choose "Immunization". Scroll
down to "Immunization: OPV 3 coverage last month". That should do.

From the title we can guess ...

1. In CommCare we need to collect data on Oral Polio Vaccine
   immunizations, associated with a location ("organisation unit" in
   DHIS2 terminology) and a date. We will track the number of doses
   given to an individual.
2. Using CommCare Data Pipeline, we export this data to a SQL database
   like PostgreSQL.
3. In Postgres we aggregate by month using a view.
4. Then we transform aggregated data into a JSON payload for DHIS2's
   DataSet API. Indicators will need to be identified by their DHIS2
   IDs.

So our next task is to find the DHIS2 IDs of the indicators for OPV 3
coverage.

Click on the ⋮⋮⋮ (3×3 grid) icon in the top right. Open "Maintenance".

#### Data element: OPV3 doses given

Open the "Data Element" tab. Click the "List" icon in the "Data
element" box.

Search "OPV". We are looking for "OPV3 doses given". Note that "Domain
type" is set to "Aggregate" (as opposed to "Tracker"). This is correct
for the type of integration we are building.

Note that "Category combination" is "Location and age group". The
CommCare app will need to collect "location" and matching "age group"
categories, and the Postgres aggregation will need to group by them.
They will be included in the API payload, identified by their "category
option combination" IDs.

Click the ⋮ (vertical ellipsis) "Actions" menu in the row for "OPV3
doses given" and choose "Show details". Note the value of "Id" is
"vI2csg55S9C".

#### Category combination: Location and age group

Next, open the "Category" tab. Click the "List" icon in the "Category
combination" box.

In the row for "Location and age group", click the ⋮ "Actions" menu and
choose "Show details". Note the value of "Id" is "dzjKKQq0cSO".

Click on the row to open "Location and age group". Note that its
"Categories" are "Location Fixed/Outreach" and "EPI/nutrition age".

Click "Cancel".

#### Category: Location Fixed/Outreach

Click "Category" in the left panel.

In the row for "Location Fixed/Outreach", click the ⋮ "Actions" menu and
choose "Show details". Note the value of "Id" is "fMZEcRHuamy". Click on
the row. Note that the "Category options" are "Fixed" and "Outreach".

Click "Cancel"

#### Category: EPI/nutrition age

In the row for "EPI/nutrition age", click the ⋮ "Actions" menu, choose
"Show details", and note that "Id" is "YNZyaJHiHYq". Click on the row,
and note that its "Category options" are "<1y" and ">1y".

#### Category option: Fixed

Click "Category option" in the left panel.

Search for "Fixed". Click the ⋮ "Actions" menu and choose "Show
details". Note the value of "Id" is "qkPbeWaFsnU".

Do the same for the other category options.

#### Category option combination: Fixed, <1y

The next DHIS2 IDs we need are for the four category option
combinations. The DHIS2 API payload will need to identify aggregation
groupings by their combination of category options.

Click "Category option combination" in the left panel. Search for
"Fixed". Get the IDs of "Fixed, <1y" and "Fixed, >1y". Do the same for
"Outreach, <1y" and "Outreach, >1y".

#### Location: Ngelehun CHC

Last, we need at least one location.

Open the "Organisation Unit" tab, and click the "List" icon in the
"Organisation units" box.

In the left panel, expand "Bo", then "Badjia", and select "Ngelehun
CHC". Open "Actions", choose "Show details", and note that its ID is
"DiszpKrYNg8".

#### Summary

Here are all the IDs we will need:

| Type                  | Name                    | ID          |
|-----------------------|-------------------------|-------------|
| Data set              | Child Health            | BfMAe6Itzgt |
| Data element          | OPV3 doses given        | vI2csg55S9C |
| Category combo        | Location and age group  | dzjKKQq0cSO |
| Category              | Location Fixed/Outreach | fMZEcRHuamy |
| Category option       | Fixed                   | qkPbeWaFsnU |
| Category option       | Outreach                | wbrDrL2aYEc |
| Category              | EPI/nutrition age       | YNZyaJHiHYq |
| Category option       | <1y                     | btOyqprQ9e8 |
| Category option       | >1y                     | GEqzEKCHoGA |
| Category option combo | Fixed, <1y              | Prlt0C1RF0s |
| Category option combo | Fixed, >1y              | psbwp3CQEhs |
| Category option combo | Outreach, <1y           | V6L425pT3A0 |
| Category option combo | Outreach, >1y           | hEFKSsPV5et |
| Organisation unit     | Ngelehun CHC            | DiszpKrYNg8 |

### Collecting data in CommCare

As a CommCare app builder, you will have an idea of what forms your app
would need for collecting these indicators. Some values, like
"vaccination_date"  

But for the sake of testing, we will skip the app building, and use a
case import instead.

In CommCare, using Data Dictionary, create two case types with the
following case properties:

#### Case type: child

| Case Property | Data Type |
|---------------|-----------|
| external_id   | Plain     |
| name          | Plain     |
| dob           | Date      |

#### Case type: vaccination

| Case Property    | Data Type       | Values          |
|------------------|-----------------|-----------------|
| vaccination_date | Date            |                 |
| child_ext_id     | Plain           |                 |
| org_unit_id      | Plain           |                 |
| location_fo      | Multiple Choice | fixed, outreach |
| opv1_dose_given  | Multiple Choice | yes, no         |
| opv2_dose_given  | Multiple Choice | yes, no         |
| opv3_dose_given  | Multiple Choice | yes, no         |

> [!Note]
> I have intentionally left DHIS2 IDs out of the data collected in
> CommCare, except for "org_unit_id". This more accurately models a
> real-world scenario, where CommCare app builders will not be using
> DHIS2 IDs for case properties in CommCare. The value for "org_unit_id"
> would come from a custom location field, named something like
> "dhis2_id", on a corresponding "Ngelehun CHC" CommCare location.

Then create two case import spreadsheets with some test data. In the
"org_unit_id" column, set all values to "DiszpKrYNg8" for "Ngelehun
CHC". Import the spreadsheets into CommCare HQ Staging.

### An example of a prompt to create a Postgres view

Using CommCare Data Pipeline, export the cases into Postgres.

Using yor favorite Postgres client:
* In the "Child" table, add an index for the "external_id" column.
* In the "Vaccination" table, set the "child_ext_id" field as a foreign
  key to "Child.external_id"

Now strike up a conversation with an LLM fluent in SQL. (Gemini, ChatGPT
or Claude are all good options. If you can choose your model, pick the
latest coding model at a medium reasoning level.) Ask it something like:

> I want to create a view in PostgreSQL to count the number of children
> who have been given an OPV3 vaccination dose. I want to aggregate them
> by organisation unit, and by age group categories "less than or equal
> to 12 months" and "greater than 12 months", and by location categories
> "fixed" and "outreach". I want a sum for each combination of those
> categories.
>
> The data is stored in two tables. The tables look like this:
>
> Child:
>
> | Field       | Type        |
> |-------------|-------------|
> | external_id | indexed key |
> | name        | string      |
> | dob         | date        |
>
> Vaccination:
>
> | Field            | Type                  | Values          |
> |------------------|-----------------------|-----------------|
> | child_ext_id     | fk: Child.external_id |                 |
> | vaccination_date | date                  |                 |
> | org_unit_id      | string                |                 |
> | location_fo      | string                | fixed, outreach |
> | opv1_dose_given  | string                | yes, no         |
> | opv2_dose_given  | string                | yes, no         |
> | opv3_dose_given  | string                | yes, no         |
>
> * Join the tables on Vaccination.child_ext_id = Child.external_id
>
> * Include only records where Vaccination.opv3_dose_given = 'yes'
>
> * Use Vaccination.vaccination_date - Child.dob to determine the age of
>   the child in months.
>
> * Allow the view to be filtered by month of Vaccination.vaccination_date.
>
> Please give me the SQL statement to create this view in PostgreSQL.
> Name it "opv3_coverage_view".

Copy and paste the SQL into your Postgres client. Test it. Continue the
conversation with the AI assistant to fix anything that isn't working
the way you want.

> [!Note]
> If you use an AI agent like Claude Code or OpenAI Codex, and a
> Postgres command line client like "psql", then the AI agent can create
> the view itself, test that it is working as you described, and fix it
> if it is not. Windows users can use Ubuntu on WSL to install these:
> * `curl -fsSL https://claude.ai/install.sh | bash`
> * `sudo apt install postgresql-client`
> Tell Claude or Codex that it can use "psql" to execute SQL commands.

> [!Warning]
> Do not give AI agents access to databases that contain real data!

### An example of a prompt to create a JSON payload view

Go back to your AI assistant, and ask it to create Postgres view that
returns a JSON payload. Maybe something like,

> I want to create a view in PostgreSQL named "opv3_coverage_payload_view".
> The new view will be queried with
> `SELECT json_payload FROM opv3_coverage_payload_view WHERE period = '{YYYYMM}';`
> where "{YYYYMM}" is a month, e.g. "202512" is December 2025.
>
> The "opv3_coverage_payload_view" view must filter "opv3_coverage_view"
> by the month given in the "period" parameter.
>
> When filtered by month, "opv3_coverage_payload_view" must return only
> one row.
>
> The "json_payload" field is a JSON object in the format of an API
> request payload. To understand the required payload format, read the
> documentation on the DHIS2 Data Values API. See the section "Sending
> bulks of data values". Note the JSON format:
> https://docs.dhis2.org/en/develop/using-the-api/dhis-core-version-239/data.html#webapi_sending_bulks_data_values
>
> Values from "opv3_coverage_view" must be transformed into uid values for
> DHIS2. Use the following mapping:
> 
> | location_fo | Age (months) | DHIS2 uid   |
> |-------------|--------------|-------------|
> | fixed       | <= 12        | Prlt0C1RF0s |
> | fixed       | > 12         | psbwp3CQEhs |
> | outreach    | <= 12        | V6L425pT3A0 |
> | outreach    | > 12         | hEFKSsPV5et |
>
> An example value of "json_payload" (DO NOT include comments):
>
> ```json
> {
>   "dataValues": [
>     {
>       "period": "202512",  // month (YYYYMM)
>       "orgUnit": "DiszpKrYNg8",  // org_unit_id
> 
>       "dataElement": "vI2csg55S9C",  // (constant) OPV3 doses given
>       "categoryOptionCombo": "Prlt0C1RF0s",  // location_fo = 'fixed', age_mo <= 12
>        
>       // The sum of OPV3 doses given to "location_fo = 'fixed', age_mo <= 12" in Dec 2025
>       "value": "12" 
>     },
>     {
>       "period": "202512",
>       "orgUnit": "DiszpKrYNg8",
> 
>       "dataElement": "vI2csg55S9C",
>       "categoryOptionCombo": "psbwp3CQEhs",  // location_fo = 'fixed', age_mo > 12
>        
>       // The sum of OPV3 doses given to "location_fo = 'fixed', age_mo > 12" in Dec 2025
>       "value": "18"
>     }
>     // ...
>   ]
> }
> ```
>
> Please use the command
> `psql -h postgres.example.com -p 5432 -u myusername -d mydatabase`
> with password "mypassword" to create this view in PostgreSQL. Query the
> view for December 2025 to verify that the value of the "json_payload"
> field is correct.

(Or just ask for the SQL statement to create the view.)

### Config for “DB Query Forwarder” to forward to DHIS2

The tricky part of configuring a data forwarder in CommCare Data
Pipeline is the query. For PostgreSQL, the following will filter
"period" by last month:

```sql
SELECT json_payload
FROM opv3_coverage_payload_view 
WHERE period = TO_CHAR(CURRENT_DATE - INTERVAL '1 month', 'YYYYMM');
```

(The query will be different for other database engines. For SQL Server
it is:

```sql
SELECT json_payload
FROM opv3_coverage_payload_view 
WHERE period = FORMAT(DATEADD(MONTH, -1, GETDATE()), 'yyyyMM');
```
)

### How to verify whether data arrived in DHIS2

Run your data forwarder. Go back to DHIS2. Check whether your graph
shows any data.

> [!Warning]
> I have not tested this! I don't know whether the graph in DHIS2 is
> actually working!
