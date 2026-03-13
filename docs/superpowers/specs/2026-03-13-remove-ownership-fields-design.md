# Remove User Ownership Fields and Fix Cascade Behavior

## Context

CDP servers are managed by a single organization. Users collaborate on
shared resources rather than owning them individually. The schema should
reflect this by removing per-user ownership foreign keys and fixing
cascade delete behavior so that deleting a CommCare account/project or
forwarding destination does not silently destroy export/forwarding
configs.

## Changes

### 1. Drop Foreign Key Fields

Remove these user-ownership columns entirely (field definition, all
references in views, forms, admin, templates, and tests):

| App        | Model                 | Field       | Current Definition           |
|------------|-----------------------|-------------|------------------------------|
| db         | Database              | owner       | FK(User, CASCADE)            |
| exports    | ExportConfigBase      | created_by  | FK(User, CASCADE)            |
| forwarding | ForwardingDestination | owner       | FK(User, CASCADE)            |
| forwarding | ForwardingConfig      | created_by  | FK(User, CASCADE)            |
| refreshes  | RefreshConfig         | created_by  | FK(User, CASCADE)            |

`ExportConfigBase` is abstract, so dropping `created_by` affects both
`ExportConfig` and `MultiProjectExportConfig` concrete tables.

### 2. Change CASCADE to PROTECT

Prevent accidental deletion of objects that are still referenced by
configs. Deletion of a referenced object will raise `ProtectedError`
instead of silently destroying the config.

| App        | Model            | Field       | Before                             | After                              |
|------------|------------------|-------------|------------------------------------|------------------------------------|
| exports    | ExportConfigBase | account     | FK(CommCareAccount, CASCADE)       | FK(CommCareAccount, PROTECT)       |
| exports    | ExportConfigBase | database    | FK(Database, CASCADE)              | FK(Database, PROTECT)              |
| exports    | ExportConfig     | project     | FK(CommCareProject, CASCADE)       | FK(CommCareProject, PROTECT)       |
| forwarding | ForwardingConfig | database    | FK(Database, CASCADE)              | FK(Database, PROTECT)              |
| forwarding | ForwardingConfig | destination | FK(ForwardingDestination, CASCADE) | FK(ForwardingDestination, PROTECT) |
| refreshes  | RefreshConfig    | database    | FK(Database, CASCADE)              | FK(Database, PROTECT)              |

Since `ExportConfigBase` is abstract, the `account` and `database`
changes affect both `ExportConfig` and `MultiProjectExportConfig`
concrete tables.

A migration is generated to record the on_delete change in Django's
migration history. PROTECT is enforced at the Django level, not the
database level, so the underlying column is unchanged.

### 3. Change SET_NULL to CASCADE

When a `Version` (django-reversion) is deleted, delete associated
`RefreshRun` records rather than orphaning them. This matches the
existing behavior of `ExportRun.export_config_version` and
`ForwardingRun.forwarding_config_version`, which already use CASCADE.

| App       | Model      | Field                  | Before                    | After                     |
|-----------|------------|------------------------|---------------------------|---------------------------|
| refreshes | RefreshRun | refresh_config_version | FK(Version, SET_NULL, null=True) | FK(Version, CASCADE, null=True) |

## Affected Files

### Models (field definitions)
- `apps/db/models.py` — drop `Database.owner`
- `apps/exports/models.py` — drop `ExportConfigBase.created_by`, change `ExportConfigBase.account`, `ExportConfigBase.database`, and `ExportConfig.project` to PROTECT
- `apps/forwarding/models.py` — drop `ForwardingDestination.owner` and `ForwardingConfig.created_by`, change `ForwardingConfig.database` and `ForwardingConfig.destination` to PROTECT
- `apps/refreshes/models.py` — drop `RefreshConfig.created_by`, change `RefreshConfig.database` to PROTECT, change `RefreshRun.refresh_config_version` to CASCADE

### Views (remove `created_by`/`owner` assignment on create)
- `apps/db/views.py` — remove `owner=request.user` assignment
- `apps/exports/views.py` — remove `created_by=request.user` assignments
- `apps/forwarding/views.py` — remove `owner=request.user` and `created_by=request.user` assignments
- `apps/refreshes/views.py` — remove `created_by=request.user` assignment

### Admin (remove from list_display, fieldsets)
- `apps/exports/admin.py` — remove `created_by` from list_display
- `apps/forwarding/admin.py` — remove `created_by` from list_display
- `apps/refreshes/admin.py` — remove `created_by` from list_display and fieldsets

### Templates (remove "Created by" display)
- `templates/db/databases.html` — remove owner column
- `templates/exports/export_details.html` — remove created_by display
- `templates/exports/exports_home.html` — remove created_by column
- `templates/exports/partials/multi_export_details.html` — remove created_by display
- `templates/forwarding/destinations.html` — remove owner column
- `templates/forwarding/forwarder_details.html` — remove created_by display
- `templates/forwarding/forwarders.html` — remove created_by column
- `templates/refreshes/refresh_details.html` — remove created_by display
- `templates/refreshes/refresh_configs.html` — remove created_by column

### Tests (remove owner/created_by from fixture creation)
- `apps/db/tests/test_models.py`
- `apps/db/tests/test_forms.py`
- `apps/exports/tests/conftest.py`
- `apps/exports/tests/fixtures.py`
- `apps/exports/tests/test_run_button_playwright.py`
- `apps/forwarding/tests/test_models.py`
- `apps/refreshes/tests/conftest.py`
- `apps/refreshes/tests/test_forms.py`
- `apps/refreshes/tests/test_models.py`
- `apps/refreshes/tests/test_views.py`
- `apps/schedules/tests/conftest.py`
- `apps/schedules/tests/test_models.py`
- `apps/schedules/tests/test_form_edit.py`

### Migrations
One new migration per app:
- `apps/db/migrations/` — remove `owner` column
- `apps/exports/migrations/` — remove `created_by` column, alter `account`, `database`, and `project` on_delete
- `apps/forwarding/migrations/` — remove `owner` and `created_by` columns, alter `database` and `destination` on_delete
- `apps/refreshes/migrations/` — remove `created_by` column, alter `database` and `refresh_config_version` on_delete

## What Does NOT Change

- `CommCareAccount.owner` (FK User, CASCADE) — unlike shared resources,
  a user genuinely owns their CommCare account credentials. Deleting a
  user should delete their account.
- `ExportRunBase.triggering_user` (FK User, SET_NULL) — tracks who
  triggered a specific run, not ownership.
- `ForwardingRun.triggering_user` — same reasoning.
- `RefreshRun.triggering_user` — same reasoning.
- `MultiProjectPartialExportRun.project` (FK CommCareProject, CASCADE)
  — run records are logs, not configs. Cascading delete is acceptable.
  A future change will add a user confirmation prompt before deleting a
  project that has linked partial export runs.
- `ExportRun.export_config_version` — already CASCADE, no change needed.
- `ForwardingRun.forwarding_config_version` — already CASCADE, no change needed.
- `MultiProjectExportRun.export_config_version` — already CASCADE, no change needed.
