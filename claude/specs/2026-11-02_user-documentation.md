# User Documentation

Replace the documentation under `docs/` with guides for the people who install
and use CommCare Data Pipeline, with a screenshot on each guide that shows the
reader where they are in the app.

## Why now

The desktop builds for Windows and macOS are published as prereleases and the
launcher runs on Linux. Pilot users are about to install the app from
`docs/pilot_guide.md` and will then look for help with the rest of the app. What
they will find today is `docs/config.md` and `docs/test_pipeline.md`, which
describe an earlier version with a different workflow (uploading config files,
Celery, Postgres as the app's own database, a production Ansible deployment),
and a README that warns that the documentation is out of date.

A previous attempt at this rewrite, on `nh/docs` and the `nh/docs-*` branches,
is the model: one task per page, a screenshot per page. Its content is stale,
but its shape and its screenshots proved their worth. This spec reuses what is
still true and drops the rest. The old branches are not merged or rebased; they
are a quarry.

## Audience

Two kinds of reader, in order of priority:

1. **A data manager or M&E officer** who knows CommCare HQ and their
   organisation's database, and is not a programmer. They install the desktop
   app, connect it to their project space and database, and set up exports. They
   may also set up a refresh or a forwarder when a data analyst or a vendor has
   created the views for them.
2. **An IT administrator** who installs the app on a shared server, manages user
   accounts, and is asked for the logs when something goes wrong.

Developers are not the audience of `docs/`. The README keeps the developer quick
start.

## Goals

- Every page that a reader needs to go from "I downloaded the app" to "my data
  arrives on schedule" exists, is true for the current code, and uses plain
  language: short sentences, "you", no jargon that the app itself does not use.
- Each guide has one screenshot of the page it talks about, so the reader can
  match the guide to what they see.
- The pilot guide stays as the entry point for pilots, and hands off to the new
  guides instead of repeating them.
- Nothing left in `docs/` or the README describes a workflow or a deployment
  that the current code does not support.

## Non-goals

- A static site or a docs build; GitHub rendering is the target.
- Teaching CommCare HQ: creating exports, apps or API keys in HQ is linked, not
  re-explained, beyond the one screen the reader must visit to find a value.
- Teaching SQL or DHIS2. The forwarding guide shows the shape of a query and a
  payload; it does not teach how to write the views.
- Translating.

## Anti-goals

- Reference-manual tone: a page per form field, or every option listed for
  completeness. Say what the field is for and what to type in the common case.
- Screenshots as a walkthrough. One per page, cropped to the panel that matters.
- Documenting the pilot's limitations as if they were permanent. Unsigned builds
  and the QA checklist belong to the pilot guide only.

## What the reader will find

### Layout

```
docs/
  index.md                     what the app does, how the pieces fit, the table of contents
  install.md                   Windows, macOS, Linux; first run; where the data and logs are; stopping; updating
  pilot_guide.md               (kept, trimmed) where to download, the warnings, the QA checklist
  add-commcare-project.md
  add-commcare-account.md
  add-database.md
  set-up-export.md
  multi-project-export.md
  schedules.md                 the schedule fields that exports, refreshes and forwarders share
  refresh-materialized-views.md
  forward-data.md              destinations and forwarders, with a DHIS2-shaped example
  monitor-runs.md              health cards, the failed-runs banner, run history, run logs, interrupted runs
  manage-users.md              adding a user, resetting a password, removing a user, your own profile
  server.md                    running on a shared server: the launcher's options, the data directory,
                               behind a proxy; moved out of the README
  troubleshooting.md           what to check first, where the logs are, what to send when asking for help
  images/<page-slug>.png       one per guide
```

Flat, not `users/` and `admin/`: the two audiences overlap and a reader should
not have to decide which they are to find a page. Each page says at the top if
it needs administrator access. In the code that is: adding, editing and deleting
a **database** or a **destination**, **Download Logs**, and everything in the
Django admin (users, CommCare servers). Projects, accounts, exports, refreshes
and forwarders are open to every signed-in user. `manage-users.md` says this
plainly, so an administrator knows what to set up for a data manager before
handing over.

Removed: `config.md`, `test_pipeline.md`, `install_docker.md`,
`install_native.md`, `install_prod.md`, `deploy_prod.md`. The pointer to the
`commcare-sync-ansible` documentation goes with them, from `docs/` and from the
README: it deploys an architecture (Celery, Redis, Postgres for the app's own
data) that this code no longer has.

### Pages

Every guide follows the same shape, from the old branch:

```markdown
# Title in sentence case

One or two sentences: what this does and when you would do it.

## Before you start

- What must already exist, each linked to its guide.

## Steps

1. Numbered steps. **UI labels in bold**, values to type in `code`, menu paths
   as **Section → Item**.

![What the picture shows](images/<slug>.png)

## Next

- The natural next guide.
```

GitHub admonitions (`> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`) for gotchas and
permission notes. Links are relative paths so they work on GitHub and in a
checkout.

`index.md` opens with a short description of what the app does and a sentence or
two on how the pieces fit: a **project** and an **account** say where the data
comes from, a **database** says where it goes, an **export** moves it, a
**refresh** rebuilds summary views in the database on a schedule, and a
**forwarder** sends the result of a query to another system. Then the table of
contents in the order a new user would read it.

`install.md` absorbs the installation sections of the pilot guide (Windows
installer and SmartScreen; macOS zip and Gatekeeper; data directory table) and
adds Linux (`uv run commcare-sync --desktop` from a checkout, as the README has
it), the first run (the setup page and the admin account), how to stop the app
(close the window; the `stop` file), what closing during a run does, and how to
update (install the new build over the old one; the data directory is kept). The
SmartScreen and Gatekeeper steps are marked as applying to unsigned builds.

`pilot_guide.md` keeps: what a pilot build is, where to download it, which macOS
zip to pick, the QA checklist, and how to report a problem. It links to
`install.md` for the installation steps and to `troubleshooting.md` for the
logs. The "Databases" section (which engines work, the SQL Server ODBC driver)
moves to `install.md`, and the driver error to `troubleshooting.md`.

`add-commcare-project.md` explains that `www.commcarehq.org` is already there as
the server, and that an organisation running its own CommCare HQ has an
administrator add it under **Admin → CommCare servers** (the Django admin), with
its name and URL. `add-commcare-account.md` shows the HQ screen where the API
key is made (**My Account Settings → API Keys**) because the key is shown only
once.

`set-up-export.md` documents the current form: the **CommCare Export** list is
fetched from HQ for the chosen project and account, the **Database**, **Batch
Size**, **Extra Arguments**, and the schedule fields by reference to
`schedules.md`. It covers **Run Now**, what the first run does (a full export)
and what later runs do (only changes since the last run: the Data Export Tool
keeps a checkpoint in the target database), and the **Start over** checkbox next
to **Run Now**, which ignores the checkpoint and exports everything again.

`multi-project-export.md` is short: when to use it (the same export from several
project spaces into one database), how it differs (tick several projects; one
account must have access to all of them; each run is one run per project under
one parent run).

`refresh-materialized-views.md` says it is PostgreSQL only, that the views must
already exist, how the view picker works, what **Concurrently** means in one
sentence (the view stays readable while it refreshes, but needs a unique index),
and the schedule.

`forward-data.md` covers both pages under **Data Forwarding**: a **destination**
(URL, method, username, password) and a **forwarder** (database, destination,
query, query parameters, schedule). It explains that the query must return the
payload to send, shows the DHIS2-shaped example from `test_pipeline.md` reduced
to the query and one payload, and links to the DHIS2 data values API and the HQ
fixture API for the two destinations the old guides covered.

`monitor-runs.md` replaces "Understanding the statistics" and "Checking the logs
for a run": the three health cards shown at the top of the Exports, Refreshes
and Forwarders pages and their thresholds (95% and 80% success over the last 24
hours, from `apps/web/stats.py`), the status banner, the run history table and
its statuses, the log viewer, the banner for runs that did not finish, and what
**Interrupted** means (the app was closed during the run; it ran again on the
next start).

`manage-users.md` is for administrators. The app has no user management pages of
its own; the guide walks through **Admin Site** in the account menu into the
Django admin: add a user (email and password), reset a password, deactivate or
delete a user, make a user an administrator (superuser). Then every user's own
**Profile** page (name, picture) and **Change password**. The login page's
**Forgot password?** link sends an email, and the app has no email server
configured in either mode, so the guide says a forgotten password is reset by an
administrator; `server.md` mentions that an email backend can be configured in
the data directory's `settings.py` and leaves the details to Django's
documentation.

`server.md` takes "Running the Launcher" from the README nearly as it is, with
the paragraphs reordered for someone installing rather than developing: install
with uv, run `commcare-sync`, the setup link, the data directory, `--port` and
`--bind`, the stop file, environment variables for the admin account, behind a
proxy, overriding settings. The README keeps a one-paragraph pointer.

`troubleshooting.md` is one page: the app does not open (a second instance opens
the browser instead; the port is taken), an export fails (open the log; the
common messages: wrong API key, wrong domain, the database refused the
connection, the SQL Server driver is missing), a run shows Interrupted, "Forgot
password?" sent nothing, how to find the data directory and zip the `logs`
folder, and the administrator-only **Download Logs** item in the account menu,
which downloads the export tool's shared `commcare_export.log` only.

### README

Remove the out-of-date warning. Keep the description, the feature list
(corrected: config files are fetched from HQ, not imported by hand), the
developer "Getting Started", and replace "Running the Launcher" with a short
paragraph and a link to `docs/server.md`. Link `docs/index.md` as the
documentation.

### Screenshots

One PNG per guide in `docs/images/`, named after the page. Taken with Playwright
from a Linux desktop instance of the current branch at a 1280 px wide viewport,
cropped to the relevant panel (the form, the table, the card row) so that text
is legible at GitHub's rendering width. Light theme. Realistic demo data: a
project space `demo`, an account `admin@example.com`, a database named
`Pipeline (PostgreSQL)`, an export of the HQ demo project's case export with a
few completed runs, a refresh of one materialized view created for the purpose,
and a destination and forwarder with the DHIS2 example. The forwarder is shown
as configured, not run: there is no DHIS2 to send to. The HQ instance is the
local development HQ at `http://localhost:8000`, added as a CommCare server in
the Django admin, with an API key made for the occasion. No real credentials
appear; the API key and password fields are masked by the browser.

The capture script is committed as `docs/screenshots.py`, in its own commit, so
that the pictures can be regenerated after a UI change. It takes the app's URL
and credentials, assumes the demo data above already exists, and writes the
PNGs. Creating the demo data is a manual, documented step at the top of the
script, not automated: it needs HQ credentials and a database.

## Constraints

- Markdown formatted with prettier (`npx prettier --write`), as CLAUDE.md asks.
- Links checked: every relative link in `docs/` and the README resolves to a
  file in the branch.
- Screenshots are the only binary files; keep each under 300 KB (crop, PNG, no
  retina scaling).
- One kind of change per commit: a commit per new page with its image, a commit
  removing each old page, a README commit, the spec added first and removed
  last.
- Browser tests are not affected; this branch has no code changes except the
  capture script, which is not imported by the app or tests.

## Left to the builder

- The exact wording of each page, within the tone above.
- Crop boundaries of each screenshot.
- Whether `schedules.md` is its own page or a section repeated in the three
  guides that use it; the spec prefers a page.
- The order of the table of contents beyond "install first, exports before
  refreshes and forwarders, administration last".

## Decisions taken with the author

- The `postgres-det` container cannot be reached: it is configured to publish
  port 5432, which the CommCare HQ Postgres container already holds, so Docker
  gave it no network. A second container, `postgres-pipeline`, listens on
  `127.0.0.1:5433` with user `postgres`, password `postgres`, database
  `postgres`, and is the database in the screenshots.
- The `commcare-sync-ansible` pointer goes entirely. Once CommCare Data Pipeline
  is rolled out, that repository will be removed.
- `docs/screenshots.py` is committed, separately from the pages.
