# Remove User Ownership Fields Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove per-user ownership foreign keys from shared resources and change cascade delete behavior to protect configs from accidental deletion.

**Architecture:** Pure schema migration — drop 5 FK columns, change 6 FKs from CASCADE to PROTECT, change 1 FK from SET_NULL to CASCADE. Each app gets one migration. All references (views, templates, admin, tests) are updated to match.

**Tech Stack:** Django 5.x, django-reversion, pytest

**Spec:** `docs/superpowers/specs/2026-03-13-remove-ownership-fields-design.md`

---

## Chunk 1: apps.db — Drop Database.owner

### Task 1: Update Database model

**Files:**
- Modify: `apps/db/models.py:11-14`

- [ ] **Step 1: Remove the `owner` field from Database model**

In `apps/db/models.py`, remove lines 11-14:

```python
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
```

Keep the `from django.conf import settings` import — it is still used by `settings.FERNET_KEYS` in the encryption logic.

- [ ] **Step 2: Remove `owner` assignment from create view**

In `apps/db/views.py:25-27`, change:

```python
            db = form.save(commit=False)
            db.owner = request.user
            db.save()
```

to:

```python
            db = form.save()
```

- [ ] **Step 3: Remove Owner column from databases template**

In `templates/db/databases.html`, remove the Owner header (line 27) and the Owner cell (lines 42-44). The table should only have the "Database" column.

Remove:
```html
            <th>{% trans "Owner" %}</th>
```

Remove:
```html
              <td>
                {% if request.user == database.owner %}{% trans "You" %}{% else %}{{ database.owner.get_display_name }}{% endif %}
              </td>
```

- [ ] **Step 4: Update tests — apps/db/tests/test_models.py**

In `apps/db/tests/test_models.py:17-19`, change:

```python
        self.db = Database(
            name='Test Database',
            owner=user,
        )
```

to:

```python
        self.db = Database(
            name='Test Database',
        )
```

The `User` import and user creation in `setup_method` (lines 11-16) are now unused — remove them:

```python
    def setup_method(self):
        User = get_user_model()
        user = User(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )
```

becomes:

```python
    def setup_method(self):
```

Also remove the `from django.contrib.auth import get_user_model` import.

- [ ] **Step 5: Update tests — apps/db/tests/test_forms.py**

In `apps/db/tests/test_forms.py`, remove `owner=self.user` from lines 37 and 59 in the `Database.objects.create()` calls. The `self.user` fixture is still needed for login in future tests, so keep the setUp method.

Actually, check: `self.user` is only used for `owner=self.user`. Remove the entire `setUp` method and `self.user` references. Change:

Line 35-37:
```python
        db = Database.objects.create(
            name='Existing DB',
            owner=self.user,
        )
```
to:
```python
        db = Database.objects.create(
            name='Existing DB',
        )
```

Line 57-59:
```python
        db = Database.objects.create(
            name='Existing DB',
            owner=self.user,
        )
```
to:
```python
        db = Database.objects.create(
            name='Existing DB',
        )
```

Remove the entire `setUp` method (lines 10-16) and the `get_user_model` import (line 1).

- [ ] **Step 6: Generate migration**

Run: `uv run python3 manage.py makemigrations db`

Expected: Creates a migration that removes the `owner` field from `Database`.

- [ ] **Step 7: Run tests**

Run: `uv run pytest apps/db/ -v`

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add apps/db/ templates/db/
git commit -m "feat: drop Database.owner foreign key

Databases are shared organization resources, not user-owned."
```

---

## Chunk 2: apps.exports — Drop created_by, change account/database/project to PROTECT

### Task 2: Update ExportConfigBase and ExportConfig models

**Files:**
- Modify: `apps/exports/models.py:17-32, 95-98`

- [ ] **Step 1: Change `account` to PROTECT and `database` to PROTECT in ExportConfigBase**

In `apps/exports/models.py`, change line 19:

```python
        on_delete=models.CASCADE,
```
to:
```python
        on_delete=models.PROTECT,
```

Change line 21:
```python
    database = models.ForeignKey('db.Database', on_delete=models.CASCADE)
```
to:
```python
    database = models.ForeignKey('db.Database', on_delete=models.PROTECT)
```

- [ ] **Step 2: Remove `created_by` from ExportConfigBase**

Remove lines 30-33:
```python
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
```

Also remove `from django.conf import settings` (line 2) since it is no longer used (check `settings` usage — `settings.COMMCARE_SYNC_EXPORT_PERIODICITY` on line 35 still uses it, so keep the import).

- [ ] **Step 3: Change `project` to PROTECT in ExportConfig**

In `apps/exports/models.py`, change line 97:

```python
        on_delete=models.CASCADE,
```
to:
```python
        on_delete=models.PROTECT,
```

- [ ] **Step 4: Remove `created_by` assignments from views**

In `apps/exports/views.py:55-57`, change:
```python
            export = form.save(commit=False)
            export.created_by = request.user
            export.save()
```
to:
```python
            export = form.save()
```

In `apps/exports/views.py:74-76`, change:
```python
            export = form.save(commit=False)
            export.created_by = request.user
            export.save()
```
to:
```python
            export = form.save()
            form.save_m2m()
```

Note: `form.save_m2m()` is on line 77, keep it after the save.

- [ ] **Step 5: Remove `created_by` from admin**

In `apps/exports/admin.py:10`, change:
```python
    list_display = ['name', 'project', 'account', 'database', 'created_by', 'is_paused', 'created_at',
                    'updated_at']
```
to:
```python
    list_display = ['name', 'project', 'account', 'database', 'is_paused', 'created_at', 'updated_at']
```

In `apps/exports/admin.py:23`, change:
```python
    list_display = ['name', 'account', 'database', 'created_by', 'is_paused', 'created_at', 'updated_at']
```
to:
```python
    list_display = ['name', 'account', 'database', 'is_paused', 'created_at', 'updated_at']
```

- [ ] **Step 6: Remove "Created By" from templates**

In `templates/exports/export_details.html`, remove lines 44-49 (the "Created By" column):
```html
      <div class="col">
        <span class="text-muted small">{% trans "Created By" %}</span>
        <h2 class="h5">
          {% if request.user == export.created_by %}{% trans "You" %}{% else %}{{ export.created_by.username }}{% endif %}
        </h2>
      </div>
```

In `templates/exports/exports_home.html`, remove the "Created By" header (line 32) and both "Created By" cells (line 51-53 for exports, line 115-117 for multi-project exports):

Remove:
```html
            <th>{% trans "Created By" %}</th>
```
(appears in both tables, lines 32 and 96)

Remove:
```html
              <td>
                {% if request.user == export.created_by %}{% trans "You" %}{% else %}{{ export.created_by.get_display_name }}{% endif %}
              </td>
```
(appears twice, lines 51-53 and 115-117)

In `templates/exports/partials/multi_export_details.html`, remove lines 45-49:
```html
    <div class="col">
      <span class="text-muted small">{% trans "Created By" %}</span>
      <h2 class="h5">
        {% if request.user == export.created_by %}{% trans "You" %}{% else %}{{ export.created_by.username }}{% endif %}
      </h2>
    </div>
```

- [ ] **Step 7: Update tests — apps/exports/tests/conftest.py**

In `apps/exports/tests/conftest.py`, remove `owner=user` from `database_db_fixture` (line 152) and remove `created_by=user` from `export_config_db_fixture` (line 175). Also remove the `user = user_fixture()` call in `database_db_fixture` (line 148) since it's no longer needed there — but check if `user_fixture` is used elsewhere in that function. It is not, so remove line 148.

In `export_config_db_fixture`, remove `user = user_fixture()` (line 161) and `created_by=user` (line 175).

- [ ] **Step 8: Update tests — apps/exports/tests/fixtures.py**

In `apps/exports/tests/fixtures.py`:

`commcare_account` fixture (line 40-45): keep as-is. `CommCareAccount.owner` is NOT being removed (it is a genuine ownership field per the spec's "What Does NOT Change" section).

`export_database` fixture (line 62-68): remove `owner=user` (line 67) and remove `user = test_user()` (line 63).

`test_data` fixture (lines 86-102): keep `owner=user` on `CommCareAccount.objects.create` (line 90) — `CommCareAccount.owner` is not changing. Remove `owner=user` only from `ExportDatabase.objects.create` (line 101).

- [ ] **Step 9: Update tests — apps/exports/tests/test_run_button_playwright.py**

In `apps/exports/tests/test_run_button_playwright.py:22-28`, remove `created_by=data['user']` (line 27):

```python
    export = ExportConfig.objects.create(
        name='Test Export',
        account=data['account'],
        project=data['project'],
        database=data['database'],
    )
```

- [ ] **Step 10: Generate migration**

Run: `uv run python3 manage.py makemigrations exports`

Expected: Creates a migration that removes `created_by`, alters `account`, `database`, and `project` on_delete.

- [ ] **Step 11: Run tests**

Run: `uv run pytest apps/exports/ -v --ignore=apps/exports/tests/test_run_button_playwright.py`

Expected: All tests pass (skip Playwright tests which need a browser).

- [ ] **Step 12: Commit**

```bash
git add apps/exports/ templates/exports/
git commit -m "feat: drop ExportConfigBase.created_by, protect account/database/project FKs

Exports are shared organization resources. PROTECT prevents accidental
deletion of referenced accounts, databases, and projects."
```

---

## Chunk 3: apps.forwarding — Drop owner/created_by, change database/destination to PROTECT

### Task 3: Update ForwardingDestination and ForwardingConfig models

**Files:**
- Modify: `apps/forwarding/models.py:32-34, 48-51, 65-67`

- [ ] **Step 1: Remove `owner` from ForwardingDestination**

In `apps/forwarding/models.py`, remove lines 32-34:
```python
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
```

- [ ] **Step 2: Change `database` and `destination` to PROTECT, remove `created_by` from ForwardingConfig**

In `apps/forwarding/models.py`, change line 48:
```python
    database = models.ForeignKey(ExportDatabase, on_delete=models.CASCADE)
```
to:
```python
    database = models.ForeignKey(ExportDatabase, on_delete=models.PROTECT)
```

Change lines 49-51:
```python
    destination = models.ForeignKey(
        ForwardingDestination, on_delete=models.CASCADE
    )
```
to:
```python
    destination = models.ForeignKey(
        ForwardingDestination, on_delete=models.PROTECT
    )
```

Remove lines 65-67:
```python
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
```

Keep the `from django.conf import settings` import — it is still used by `ForwardingRun.triggering_user` which references `settings.AUTH_USER_MODEL`.

- [ ] **Step 3: Remove `owner` and `created_by` assignments from views**

In `apps/forwarding/views.py:44-46`, change:
```python
            with transaction.atomic():
                config = config_form.save(commit=False)
                config.created_by = request.user
                config.save()
```
to:
```python
            with transaction.atomic():
                config = config_form.save()
```

In `apps/forwarding/views.py:151-153`, change:
```python
            destination = form.save(commit=False)
            destination.owner = request.user
            destination.save()
```
to:
```python
            destination = form.save()
```

- [ ] **Step 4: Remove `created_by` from admin**

In `apps/forwarding/admin.py:12`, change:
```python
    list_display = ['name', 'database', 'destination', 'created_by', 'created_at', 'updated_at']
```
to:
```python
    list_display = ['name', 'database', 'destination', 'created_at', 'updated_at']
```

- [ ] **Step 5: Remove "Owner" and "Created By" from templates**

In `templates/forwarding/destinations.html`, remove Owner header (line 27) and Owner cell (lines 45-47):

Remove:
```html
            <th>{% trans "Owner" %}</th>
```

Remove:
```html
              <td>
                {% if request.user == destination.owner %}{% trans "You" %}{% else %}{{ destination.owner.get_display_name }}{% endif %}
              </td>
```

In `templates/forwarding/forwarder_details.html`, remove lines 35-39:
```html
      <div class="col">
        <span class="text-muted small">{% trans "Created By" %}</span>
        <h2 class="h5">
          {% if request.user == forwarder.created_by %}{% trans "You" %}{% else %}{{ forwarder.created_by.username }}{% endif %}
        </h2>
      </div>
```

In `templates/forwarding/forwarders.html`, remove "Created By" header (line 22) and cell (lines 42-44):

Remove:
```html
            <th>{% trans "Created By" %}</th>
```

Remove:
```html
              <td>
                {% if request.user == forwarder.created_by %}{% trans "You" %}{% else %}{{ forwarder.created_by.get_display_name }}{% endif %}
              </td>
```

- [ ] **Step 6: Update tests — apps/forwarding/tests/test_models.py**

This file has many fixtures creating `owner=self.user` and `created_by=self.user`. Apply these changes throughout:

In `TestForwardingConfig.setup_method` (lines 29-45): remove `owner=self.user` from `ExportDatabase.objects.create` (line 32) and `ForwardingDestination.objects.create` (line 37), remove `created_by=self.user` from `ForwardingConfig.objects.create` (line 44).

In `TestForwardingRun.setup_method` (lines 146-162): same pattern — remove `owner=self.user` from lines 149, 154, remove `created_by=self.user` from line 161.

In `TestExportDatabase.test_str_method` (line 284): remove `owner=self.user`.

In `TestForwardingDestination` (lines 299, 308, 319): remove `owner=self.user` from all `ForwardingDestination.objects.create` calls.

In `TestForwardingScheduling.setup_method` (lines 337-346): remove `owner=self.user` from lines 340 and 345.

In all `ForwardingConfig.objects.create` calls in `TestForwardingScheduling` (lines 356, 378, 400, 412, 434, 452, 474, 485, 503, 518): remove `created_by=self.user`.

- [ ] **Step 7: Update tests — apps/schedules/tests/conftest.py**

In `apps/schedules/tests/conftest.py`, remove `owner=user` from the `database` fixture (line 22) and `destination` fixture (line 31).

- [ ] **Step 8: Update tests — apps/schedules/tests/test_models.py**

In `apps/schedules/tests/test_models.py`:

`ScheduleMixinTestBase.setUp` (lines 28-37): remove `owner=self.user` from `ExportDatabase.objects.create` (line 31) and `ForwardingDestination.objects.create` (line 35).

`ScheduleMixinTestBase._make_config` (line 46): remove `created_by=self.user`.

`ScheduleEdgeCasesTestCase.test_multiple_configs_reuse_celery_schedules` (line 294): remove `created_by=self.user` from the `ForwardingConfig.objects.create` call for `config2`.

`ScheduleValidationTestCase._make_unsaved_config` (line 329): remove `created_by=self.user`.

- [ ] **Step 9: Update tests — apps/schedules/tests/test_form_edit.py**

In `apps/schedules/tests/test_form_edit.py`, remove `created_by=user` from all `ForwardingConfig.objects.create` calls (lines 22, 42, 61, 98).

- [ ] **Step 10: Generate migration**

Run: `uv run python3 manage.py makemigrations forwarding`

Expected: Creates a migration that removes `owner` from ForwardingDestination, removes `created_by` from ForwardingConfig, alters `database` and `destination` on_delete.

- [ ] **Step 11: Run tests**

Run: `uv run pytest apps/forwarding/ apps/schedules/ -v`

Expected: All tests pass.

- [ ] **Step 12: Commit**

```bash
git add apps/forwarding/ apps/schedules/ templates/forwarding/
git commit -m "feat: drop forwarding ownership fields, protect database/destination FKs

ForwardingDestination.owner and ForwardingConfig.created_by removed.
PROTECT prevents accidental deletion of referenced databases and
destinations."
```

---

## Chunk 4: apps.refreshes — Drop created_by, change database to PROTECT, change refresh_config_version to CASCADE

### Task 4: Update RefreshConfig and RefreshRun models

**Files:**
- Modify: `apps/refreshes/models.py:24, 43-45, 102-106`

- [ ] **Step 1: Change `database` to PROTECT and remove `created_by` from RefreshConfig**

In `apps/refreshes/models.py`, change line 25:
```python
        on_delete=models.CASCADE,
```
to:
```python
        on_delete=models.PROTECT,
```

Remove lines 43-45:
```python
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
```

Keep the `from django.conf import settings` import — it is still used by `RefreshRun.triggering_user` which references `settings.AUTH_USER_MODEL`.

- [ ] **Step 2: Change `refresh_config_version` to CASCADE in RefreshRun**

In `apps/refreshes/models.py`, change line 104:
```python
        on_delete=models.SET_NULL,
```
to:
```python
        on_delete=models.CASCADE,
```

- [ ] **Step 3: Remove `created_by` assignment from view**

In `apps/refreshes/views.py:48-50`, change:
```python
            with transaction.atomic():
                config = config_form.save(commit=False)
                config.created_by = request.user
                config.save()
```
to:
```python
            with transaction.atomic():
                config = config_form.save()
```

- [ ] **Step 4: Remove `created_by` from admin**

In `apps/refreshes/admin.py:10-15`, change:
```python
    list_display = [
        'name',
        'database',
        'created_by',
        'created_at',
        'updated_at',
    ]
```
to:
```python
    list_display = [
        'name',
        'database',
        'created_at',
        'updated_at',
    ]
```

In `apps/refreshes/admin.py:23-28`, remove `'created_by'` from fieldsets:
```python
                'fields': (
                    'name',
                    'database',
                    'materialized_views',
                    'created_by',
                )
```
to:
```python
                'fields': (
                    'name',
                    'database',
                    'materialized_views',
                )
```

- [ ] **Step 5: Remove "Created By" from templates**

In `templates/refreshes/refresh_details.html`, remove lines 31-35:
```html
      <div class="col">
        <span class="text-muted small">{% trans "Created By" %}</span>
        <h2 class="h5">
          {% if request.user == config.created_by %}{% trans "You" %}{% else %}{{ config.created_by.username }}{% endif %}
        </h2>
      </div>
```

In `templates/refreshes/refresh_configs.html`, remove "Created By" header (line 23) and cell (lines 42-44):

Remove:
```html
            <th>{% trans "Created By" %}</th>
```

Remove:
```html
              <td>
                {% if request.user == config.created_by %}{% trans "You" %}{% else %}{{ config.created_by.get_display_name }}{% endif %}
              </td>
```

- [ ] **Step 6: Update tests — apps/refreshes/tests/conftest.py**

In `apps/refreshes/tests/conftest.py`:

`database` fixture (lines 19-24): remove `owner=user` (line 23). Also remove the `user` parameter from the fixture signature since it's no longer needed:
```python
@pytest.fixture
def database(db):
    return ExportDatabase.objects.create(
        name='Test PostgreSQL',
        connection_string='postgresql://localhost/test',
    )
```

`refresh_config` fixture (lines 27-34): remove `created_by=user` (line 33). Remove the `user` parameter from the fixture signature:
```python
@pytest.fixture
def refresh_config(db, database):
    return RefreshConfig.objects.create(
        name='Test Refresh Config',
        database=database,
        materialized_views=['public.view1', 'public.view2'],
    )
```

- [ ] **Step 7: Update tests — apps/refreshes/tests/test_forms.py**

In `apps/refreshes/tests/test_forms.py`:

`test_create_with_valid_data` (lines 24-40): remove `config.created_by = user` (line 36) and remove `user` from the method signature. Change:
```python
    def test_create_with_valid_data(self, user, database):
```
to:
```python
    def test_create_with_valid_data(self, database):
```

`test_create_rejects_non_postgresql_database` (lines 69-85): remove `owner=user` from `ExportDatabase.objects.create` (line 73). Remove `user` from method signature.

`test_edit_populates_materialized_views` (lines 87-99): remove `created_by=user` from `RefreshConfig.objects.create` (line 92). Remove `user` from method signature.

`test_edit_saves_updated_views` (lines 101-122): remove `created_by=user` from `RefreshConfig.objects.create` (line 106). Remove `user` from method signature.

- [ ] **Step 8: Update tests — apps/refreshes/tests/test_models.py**

In `apps/refreshes/tests/test_models.py`:

`test_validation_rejects_non_postgresql` (lines 69-83): remove `owner=user` from `ExportDatabase.objects.create` (line 72) and `created_by=user` from `RefreshConfig()` (line 79). Remove `user` from method signature.

`test_validation_rejects_empty_views` (lines 85-94): remove `created_by=user` from `RefreshConfig()` (line 90). Remove `user` from method signature.

- [ ] **Step 9: Update tests — apps/refreshes/tests/test_views.py**

In `apps/refreshes/tests/test_views.py`:

`non_pg_database` fixture (lines 24-29): remove `owner=user` (line 28). Remove `user` from fixture signature:
```python
@pytest.fixture
def non_pg_database(db):
    return ExportDatabase.objects.create(
        name='MySQL DB',
        connection_string='mysql://localhost/test',
    )
```

- [ ] **Step 10: Generate migration**

Run: `uv run python3 manage.py makemigrations refreshes`

Expected: Creates a migration that removes `created_by` from RefreshConfig, alters `database` on_delete to PROTECT, alters `refresh_config_version` on_delete to CASCADE.

- [ ] **Step 11: Run tests**

Run: `uv run pytest apps/refreshes/ -v`

Expected: All tests pass.

- [ ] **Step 12: Commit**

```bash
git add apps/refreshes/ templates/refreshes/
git commit -m "feat: drop RefreshConfig.created_by, protect database FK, cascade config version

PROTECT on database prevents accidental deletion. CASCADE on
refresh_config_version matches export and forwarding run behavior."
```

---

## Chunk 5: Final verification

### Task 5: Run full test suite and verify migrations

- [ ] **Step 1: Run makemigrations check**

Run: `uv run python3 manage.py makemigrations --check`

Expected: "No changes detected" — all model changes have corresponding migrations.

- [ ] **Step 2: Run full test suite (excluding Playwright)**

Run: `uv run pytest --ignore=apps/exports/tests/test_run_button_playwright.py -v`

Expected: All tests pass.

- [ ] **Step 3: Run mypy**

Run: `uv run mypy apps/ commcare_sync/ *.py`

Expected: No new type errors.

- [ ] **Step 4: Run ruff**

Run: `uv run ruff check`

Expected: No linting errors.

- [ ] **Step 5: Commit any fixes if needed**

If any verification step revealed issues, fix and commit.
