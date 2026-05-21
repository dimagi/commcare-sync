# User and admin documentation rewrite

## Background

The existing `docs/` directory mixes documentation for three audiences
(developers, sysadmins/devops, end users) and much of the content is outdated.
This spec covers replacing it with audience-organised, task-oriented guides
under `docs/`, plus a single combined developer setup doc at the repo root.

## Goals

- Provide task-oriented guides for **regular users** and **admin users** of
  CommCare Data Pipeline.
- Replace the two competing developer setup paths (`install_docker.md`,
  `install_native.md`) with a single `DEV_SETUP.md` at the repo root that uses
  Docker for Postgres and Redis and runs Celery and the webserver natively
  inside `tmux`.
- Replace the production install/deploy docs with a one-line pointer to the
  existing ansible documentation.
- Make docs comfortable to read on GitHub (GFM, including `> [!NOTE]`
  admonitions).

## Non-goals

- Creating a materialized view (referenced only as a prerequisite).
- Mapping aggregated data to a DHIS2 JSON payload (referenced only as a
  prerequisite).
- Building or exporting documentation to a static site — GitHub rendering is the
  target.

## Audience assumptions

- **Regular user guides** assume familiarity with CommCare HQ (project spaces,
  API keys, app structure). HQ-side prerequisites are linked out rather than
  re-explained.
- **Admin user guides** assume the reader has CommCare Data Pipeline
  admin/superuser access and basic comfort with a web admin UI.
- **`DEV_SETUP.md`** assumes a Linux/macOS developer comfortable with `git`,
  `uv`, Docker, and `tmux`.

## File layout

```
docs/
  index.md
  users/
    add-commcare-project.md
    add-commcare-account.md
    add-database.md
    set-up-export.md
    schedule-materialized-view-refresh.md
    forward-to-dhis2.md
    forward-to-commcare-fixture.md
    understanding-statistics.md
    checking-run-logs.md
  admin/
    add-user.md
    reset-password.md
    delete-user.md
    add-commcare-server.md
    download-pipeline-logs.md
  images/
    <one PNG per guide, slug-matched>
DEV_SETUP.md          (new, at repo root)
```

`docs/index.md` is a grouped table of contents:

- **User guides** — links to each `docs/users/*.md`
- **Admin guides** — links to each `docs/admin/*.md`
- **Development** — link to `../DEV_SETUP.md`
- **Production** — one-line pointer to
  <https://commcare-sync-ansible.readthedocs.io/en/latest/system-administration.html>

### Files removed

- `docs/install_docker.md` — replaced by `DEV_SETUP.md`
- `docs/install_native.md` — replaced by `DEV_SETUP.md`
- `docs/install_prod.md` — replaced by ansible-docs link in `docs/index.md`
- `docs/deploy_prod.md` — replaced by ansible-docs link in `docs/index.md`
- `docs/config.md` — content redistributed into the per-feature user guides
- `docs/test_pipeline.md` — accurate content salvaged into `set-up-export.md`;
  rest deleted

### Root `README.md`

Update any links pointing at the removed `docs/install*.md` to point at
`DEV_SETUP.md` and `docs/index.md`.

## Per-guide template

Every guide under `docs/users/` and `docs/admin/` follows this template:

```markdown
# <Title in sentence case>

<1–2 sentence "what this does and when you'd do it">

## Prerequisites

- Bullet list of what must already exist.
- HQ-side prerequisites linked out, not re-explained.

## Steps

1. Numbered step. UI labels in **bold**, values to type in `code`.
2. ...

![Caption](../images/<guide-slug>.png)

## Next steps

- Link to the natural follow-on guide(s).
```

Conventions:

- **GFM admonitions** (`> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`) for
  prerequisites callouts, permission notes, and gotchas.
- **One screenshot per guide max**, captured at 1280px wide, cropped to the
  relevant panel, stored in `docs/images/<guide-slug>.png`. The screenshot
  anchors the reader at the right page; it is not a step-by-step visual
  walkthrough.
- **UI labels in bold**, **values to type in `code`**, menu paths written as
  **Top menu → Sub-item**.
- **Internal links** use repository-relative paths so they work in GitHub and in
  checkouts.

## Guide inventory

### User guides (`docs/users/`)

| Guide                                   | Purpose                                                                                            | Key prerequisites                                                                                                                |
| --------------------------------------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `add-commcare-project.md`               | Register a CommCare HQ project space with the pipeline.                                            | A CommCare HQ server registered (admin task).                                                                                    |
| `add-commcare-account.md`               | Add credentials (username + API key) used to pull data from HQ.                                    | A CommCare Project.                                                                                                              |
| `add-database.md`                       | Register a target Postgres database where exported data will land.                                 | Network access to a Postgres instance.                                                                                           |
| `set-up-export.md`                      | Configure and run a Data Export Tool export from HQ into a database.                               | Project, Account, Database. Inherits accurate content from `test_pipeline.md`.                                                   |
| `schedule-materialized-view-refresh.md` | Schedule periodic refresh of an existing materialised view.                                        | A materialised view already created (out of scope).                                                                              |
| `forward-to-dhis2.md`                   | Configure a forwarding rule that sends aggregated data to DHIS2.                                   | An export producing the right shape; a DHIS2 endpoint + dataset ID + credentials.                                                |
| `forward-to-commcare-fixture.md`        | Configure a forwarding rule that updates a CommCare lookup-table (fixture) via the HQ fixture API. | A fixture in HQ; an HQ API key with permission to edit fixtures. Links to <https://commcare-hq.readthedocs.io/api/fixture.html>. |
| `understanding-statistics.md`           | Reference for what each statistic on a run/export page means.                                      | At least one completed run to see real numbers.                                                                                  |
| `checking-run-logs.md`                  | How to view run logs for a specific export/forwarding run, including filtering by status.          | An export or forwarding run that has executed.                                                                                   |

### Admin guides (`docs/admin/`)

| Guide                       | Purpose                                                            | Key prerequisites                                          |
| --------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------- |
| `add-user.md`               | Create a new user account.                                         | Admin access.                                              |
| `reset-password.md`         | Reset another user's password.                                     | Admin access.                                              |
| `delete-user.md`            | Remove a user account.                                             | Admin access; awareness of any data the user owns.         |
| `add-commcare-server.md`    | Register a CommCare HQ server instance the pipeline can pull from. | Admin access. Referenced as a prerequisite by user guides. |
| `download-pipeline-logs.md` | Retrieve CommCare Data Pipeline application logs.                  | Admin access.                                              |

## DEV_SETUP.md

Single combined developer setup doc at the repo root. Structure:

1. **Prerequisites** — Python (version per `pyproject.toml`), `uv`, Docker +
   Docker Compose, `tmux`, `npm`.
2. **Clone and install** — `git clone`, `uv sync`, frontend asset install
   (`npm install`).
3. **Run the stack in tmux** — the user-provided script (verbatim, with
   explanation of each window):
   - `docker` window: `docker-compose up db redis`
   - `worker` window: `celery -A commcare_sync worker -l INFO -B`
   - `runserver` window: `./manage.py runserver 0.0.0.0:8001`
4. **First-time database setup** — `./manage.py migrate`, create superuser.
5. **Running tests** — `uv run pytest`, Playwright setup notes pulled from the
   existing `apps/exports/tests/conftest.py`.
6. **Common tasks** — formatting (`ruff`, `prettier`), typing (`mypy`), linting.
7. **Troubleshooting** — port conflicts on 5432 / 6379 / 8001, common Docker
   pitfalls.

Keep the tmux script as a copy-pastable block so a developer can `chmod +x` and
run it.

## Content sources and verification

For every guide:

1. **Walk the flow in Playwright** against the running app at
   `http://127.0.0.1:8001/` as canonical source of truth. Capture exact button
   labels, field names, menu paths, validation messages.
2. **Cross-check `config.md` and `test_pipeline.md`** for prerequisites or
   gotchas the live UI doesn't surface. Fold in what's still accurate; drop what
   isn't.
3. **For forwarding guides (DHIS2, fixture)**: verify the configuration UI
   end-to-end. Stop short of pushing to a live external endpoint. Document what
   the user must obtain and link to relevant HQ/DHIS2 docs.
4. **For `understanding-statistics.md`**: trigger at least one export run so the
   stats panel has real numbers, then document each field by what it actually
   shows.
5. **Capture one screenshot per guide** at the moment the template describes —
   usually the landing page of the feature.

Verification accounts:

- Existing `admin@example.com` / `Passw0rd!` for admin flows.
- New `regular@example.com` / `Passw0rd!` for verifying the user-vs-admin
  permission split.
- A new Postgres database created on `localhost:5432` (user `commcarehq`,
  password `commcarehq`) for the "Add a database" and export walkthroughs.

## Sequencing

Spec → plan → one PR per guide.

PR order (each PR self-contained but earlier ones unblock review patterns for
later):

1. **Scaffolding** — new `docs/index.md`, create `docs/users/` + `docs/admin/`
   with placeholder READMEs, delete `install_prod.md` and `deploy_prod.md`,
   update root `README.md` links.
2. **DEV_SETUP.md** — merged dev install doc; delete `install_docker.md` +
   `install_native.md`.
3. **Admin: `add-commcare-server.md`** — promoted earlier because user guides
   reference it as a prerequisite.
4. **User guides**, in dependency order:
   1. `add-commcare-project.md`
   2. `add-commcare-account.md`
   3. `add-database.md`
   4. `set-up-export.md`
   5. `understanding-statistics.md`
   6. `checking-run-logs.md`
   7. `schedule-materialized-view-refresh.md`
   8. `forward-to-dhis2.md`
   9. `forward-to-commcare-fixture.md`
5. **Remaining admin guides**: `add-user.md`, `reset-password.md`,
   `delete-user.md`, `download-pipeline-logs.md`.
6. **Cleanup** — delete `config.md` and `test_pipeline.md` once their content
   has been redistributed.

## Success criteria

- A new user with CommCare HQ experience but no CommCare Data Pipeline
  experience can complete the "set up an export" path end-to-end using only
  `docs/index.md` and the guides it links to.
- An admin user can create another user, reset that user's password, and
  retrieve application logs using only the admin guides.
- A new developer can stand up a working local environment using only
  `DEV_SETUP.md`.
- No guide depends on content from `config.md`, `test_pipeline.md`,
  `install_docker.md`, `install_native.md`, `install_prod.md`, or
  `deploy_prod.md` once the rewrite is complete.
