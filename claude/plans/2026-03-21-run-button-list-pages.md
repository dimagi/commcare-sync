# Run Button on List Pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a ▶ Run button to the Actions column on the Exports, Refreshes, and Forwarders list pages, with per-row optimistic progress feedback driven by Alpine.js.

**Architecture:** Each config-table partial gets a Run button that fires `hx-post` to the existing run endpoint with `hx-swap="none"`. Alpine.js sets `running=true` immediately on click, swapping the Status cell to a spinner; the existing 60-second HTMX poll resets it when the server-side status changes. Model properties (`is_multi_project`, `has_active_run`) drive server-rendered disabled states.

**Tech Stack:** Django, Alpine.js, HTMX, Bootstrap 5, pytest, Playwright

**Spec:** `claude/specs/2026-03-21-run-button-list-pages.md`

---

## File map

| File | Change |
|---|---|
| `apps/exports/models.py` | Add `is_multi_project` to `ExportConfigBase`/`MultiProjectExportConfig`; add `has_active_run` to `ExportConfigBase` |
| `apps/refreshes/models.py` | Add `has_active_run` to `RefreshConfig` |
| `apps/forwarding/models.py` | Add `has_active_run` to `ForwardingConfig` |
| `apps/exports/views.py` | Add HTMX branch to `run_export`, `run_multi_export` |
| `apps/refreshes/views.py` | Add HTMX branch to `run_refresh` |
| `apps/forwarding/views.py` | Add HTMX branch to `run_forwarding` |
| `templates/exports/partials/config_table.html` | Add Run button; add spinner branch to Status cell |
| `templates/refreshes/partials/config_table.html` | Same |
| `templates/forwarding/partials/config_table.html` | Same |
| `apps/exports/tests/test_list_view.py` | Tests for `is_multi_project`, `has_active_run`, run view HTMX branch, template rendering |
| `apps/refreshes/tests/test_models.py` | Tests for `has_active_run` on `RefreshConfig` |
| `apps/refreshes/tests/test_views.py` | Tests for HTMX branch in `run_refresh` |
| `apps/forwarding/tests/test_models.py` | Tests for `has_active_run` on `ForwardingConfig` |
| `apps/forwarding/tests/test_views.py` | Tests for HTMX branch in `run_forwarding` |
| `apps/exports/tests/test_list_view_run_button_playwright.py` | New Playwright test for Run button on list page |

---

## Task 1: `is_multi_project` property on export config models

**Files:**
- Modify: `apps/exports/models.py:12-80` (`ExportConfigBase`), `:96-124` (`MultiProjectExportConfig`)
- Test: `apps/exports/tests/test_list_view.py` (add to `TestExportConfigBaseProperties`)

- [ ] **Step 1: Write the failing tests**

Add a **new** test class in `apps/exports/tests/test_list_view.py` (do not add to `TestExportConfigBaseProperties` — that class has no `@pytest.mark.django_db` decorator):

```python
@pytest.mark.django_db
class TestIsMultiProject:
    def test_export_config_is_not_multi_project(self, export_config):
        assert export_config.is_multi_project is False

    def test_multi_export_config_is_multi_project(self, multi_export_config):
        assert multi_export_config.is_multi_project is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest apps/exports/tests/test_list_view.py::TestIsMultiProject -v --no-migrations
```

Expected: FAIL — `AttributeError: 'ExportConfig' object has no attribute 'is_multi_project'`

- [ ] **Step 3: Add `is_multi_project` to models**

In `apps/exports/models.py`, add to `ExportConfigBase` (after the `details_url` property, before `save`):

```python
@property
def is_multi_project(self):
    return False
```

Add to `MultiProjectExportConfig` (after `get_projects_display_short`):

```python
@property
def is_multi_project(self):
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest apps/exports/tests/test_list_view.py::TestIsMultiProject -v --no-migrations
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/exports/models.py apps/exports/tests/test_list_view.py
git commit -m "feat: add is_multi_project property to ExportConfigBase / MultiProjectExportConfig"
```

---

## Task 2: `has_active_run` on `ExportConfigBase`

**Files:**
- Modify: `apps/exports/models.py:12-80` (`ExportConfigBase`)
- Test: `apps/exports/tests/test_list_view.py`

- [ ] **Step 1: Write the failing tests**

Add a new test class in `apps/exports/tests/test_list_view.py`:

```python
@pytest.mark.django_db
class TestExportConfigHasActiveRun:
    def test_false_with_no_runs(self, export_config):
        assert export_config.has_active_run is False

    def test_false_when_run_is_completed(self, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.COMPLETED,
        )
        assert export_config.has_active_run is False

    def test_false_when_run_is_failed(self, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.FAILED,
        )
        assert export_config.has_active_run is False

    def test_true_when_run_is_queued(self, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.QUEUED,
        )
        assert export_config.has_active_run is True

    def test_true_when_run_is_started(self, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.STARTED,
        )
        assert export_config.has_active_run is True

    def test_uses_prefetched_runs_without_db_query(self, export_config):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        run = ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.QUEUED,
        )
        export_config._all_runs = [run]
        with CaptureQueriesContext(connection) as ctx:
            result = export_config.has_active_run
        assert len(ctx) == 0
        assert result is True

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest apps/exports/tests/test_list_view.py::TestExportConfigHasActiveRun -v --no-migrations
```

Expected: FAIL — `AttributeError: 'ExportConfig' object has no attribute 'has_active_run'`

- [ ] **Step 3: Add `has_active_run` to `ExportConfigBase`**

In `apps/exports/models.py`, add to `ExportConfigBase` after `last_run`:

```python
@property
def has_active_run(self):
    active = {ExportRun.Status.QUEUED, ExportRun.Status.STARTED}
    all_runs = getattr(self, '_all_runs', None)
    if all_runs is not None:
        return any(r.status in active for r in all_runs)
    return self.runs.filter(status__in=active).exists()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest apps/exports/tests/test_list_view.py::TestExportConfigHasActiveRun -v --no-migrations
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/exports/models.py apps/exports/tests/test_list_view.py
git commit -m "feat: add has_active_run property to ExportConfigBase"
```

---

## Task 3: `has_active_run` on `RefreshConfig`

**Files:**
- Modify: `apps/refreshes/models.py` (`RefreshConfig`)
- Test: `apps/refreshes/tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Add a new test class in `apps/refreshes/tests/test_models.py`:

```python
@pytest.mark.django_db
class TestRefreshConfigHasActiveRun:
    def test_false_with_no_runs(self, refresh_config):
        assert refresh_config.has_active_run is False

    def test_false_when_run_is_completed(self, refresh_config):
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.COMPLETED,
        )
        assert refresh_config.has_active_run is False

    def test_false_when_run_is_failed(self, refresh_config):
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.FAILED,
        )
        assert refresh_config.has_active_run is False

    def test_true_when_run_is_queued(self, refresh_config):
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.QUEUED,
        )
        assert refresh_config.has_active_run is True

    def test_true_when_run_is_started(self, refresh_config):
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.STARTED,
        )
        assert refresh_config.has_active_run is True

    def test_uses_prefetched_runs_without_db_query(self, refresh_config):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        run = RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.QUEUED,
        )
        refresh_config._all_runs = [run]
        with CaptureQueriesContext(connection) as ctx:
            result = refresh_config.has_active_run
        assert len(ctx) == 0
        assert result is True
```

The `refresh_config` fixture is defined in `apps/refreshes/tests/conftest.py` — use it directly.

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest apps/refreshes/tests/test_models.py::TestRefreshConfigHasActiveRun -v --no-migrations
```

Expected: FAIL — `AttributeError: 'RefreshConfig' object has no attribute 'has_active_run'`

- [ ] **Step 3: Add `has_active_run` to `RefreshConfig`**

In `apps/refreshes/models.py`, add after `last_run`:

```python
@property
def has_active_run(self):
    active = {RefreshRun.Status.QUEUED, RefreshRun.Status.STARTED}
    all_runs = getattr(self, '_all_runs', None)
    if all_runs is not None:
        return any(r.status in active for r in all_runs)
    return self.runs.filter(status__in=active).exists()
```

`RefreshRun.Status` resolves via Python MRO from `RunBaseModel.Status` — `RefreshRun` does not define its own `Status`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest apps/refreshes/tests/test_models.py::TestRefreshConfigHasActiveRun -v --no-migrations
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/refreshes/models.py apps/refreshes/tests/test_models.py
git commit -m "feat: add has_active_run property to RefreshConfig"
```

---

## Task 4: `has_active_run` on `ForwardingConfig`

**Files:**
- Modify: `apps/forwarding/models.py` (`ForwardingConfig`)
- Test: `apps/forwarding/tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Add a new test class in `apps/forwarding/tests/test_models.py`. The existing test class uses `setup_method` to create fixtures directly — follow the same pattern:

```python
@pytest.mark.django_db(transaction=True)
class TestForwardingConfigHasActiveRun:
    def setup_method(self):
        self.database = Database.objects.create(
            name='Test DB',
            connection_string='postgresql://localhost/test',
        )
        self.destination = ForwardingDestination.objects.create(
            name='Test API',
            api_url='https://example.com/api',
        )
        self.config = ForwardingConfig.objects.create(
            name='Test Config',
            database=self.database,
            destination=self.destination,
            query='SELECT 1',
        )

    def test_false_with_no_runs(self):
        assert self.config.has_active_run is False

    def test_false_when_run_is_completed(self):
        ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.COMPLETED,
        )
        assert self.config.has_active_run is False

    def test_false_when_run_is_failed(self):
        ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.FAILED,
        )
        assert self.config.has_active_run is False

    def test_true_when_run_is_queued(self):
        ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.QUEUED,
        )
        assert self.config.has_active_run is True

    def test_true_when_run_is_started(self):
        ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.STARTED,
        )
        assert self.config.has_active_run is True

    def test_uses_prefetched_runs_without_db_query(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        run = ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.QUEUED,
        )
        self.config._all_runs = [run]
        with CaptureQueriesContext(connection) as ctx:
            result = self.config.has_active_run
        assert len(ctx) == 0
        assert result is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest apps/forwarding/tests/test_models.py::TestForwardingConfigHasActiveRun -v --no-migrations
```

Expected: FAIL — `AttributeError: 'ForwardingConfig' object has no attribute 'has_active_run'`

- [ ] **Step 3: Add `has_active_run` to `ForwardingConfig`**

In `apps/forwarding/models.py`, add after `last_run`:

```python
@property
def has_active_run(self):
    active = {ForwardingRun.Status.QUEUED, ForwardingRun.Status.STARTED}
    all_runs = getattr(self, '_all_runs', None)
    if all_runs is not None:
        return any(r.status in active for r in all_runs)
    return self.runs.filter(status__in=active).exists()
```

`ForwardingRun.Status` resolves via Python MRO from `RunBaseModel.Status`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest apps/forwarding/tests/test_models.py::TestForwardingConfigHasActiveRun -v --no-migrations
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/forwarding/models.py apps/forwarding/tests/test_models.py
git commit -m "feat: add has_active_run property to ForwardingConfig"
```

---

## Task 5: HTMX branch in `run_export` and `run_multi_export`

**Files:**
- Modify: `apps/exports/views.py:463-501`
- Test: `apps/exports/tests/test_list_view.py`

**Background:** Both views currently call `json.loads(request.body)`. HTMX sends `application/x-www-form-urlencoded` (not JSON), so the parse raises `JSONDecodeError` when called from the Run button. Fix: when `HX-Request` header is present, skip the JSON parse and always use `force_sync=False`; return `204` instead of the task-ID body.

- [ ] **Step 1: Write the failing tests**

Add a new test class `TestRunExportHtmxBranch` in `apps/exports/tests/test_list_view.py`:

```python
@pytest.mark.django_db
class TestRunExportHtmxBranch:
    def test_htmx_request_returns_204(self, client, export_config):
        url = reverse('exports:run_export', args=[export_config.id])
        response = client.post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    def test_htmx_request_creates_export_run(self, client, export_config):
        url = reverse('exports:run_export', args=[export_config.id])
        client.post(url, HTTP_HX_REQUEST='true')
        assert ExportRun.objects.filter(
            base_export_config=export_config,
            triggered_from_ui=True,
        ).exists()

    def test_non_htmx_request_returns_200_with_task_id(
        self, client, export_config
    ):
        import json
        url = reverse('exports:run_export', args=[export_config.id])
        response = client.post(
            url,
            data=json.dumps({'forceSync': False}),
            content_type='application/json',
        )
        assert response.status_code == 200
        assert len(response.content) > 0  # task ID in body

    def test_non_htmx_force_sync_true_passes_flag(
        self, client, export_config
    ):
        """forceSync: true in JSON body passes force_sync_all_data=True to task."""
        import json
        from unittest.mock import patch
        url = reverse('exports:run_export', args=[export_config.id])
        with patch('apps.exports.views.run_export_task') as mock_task:
            mock_task.delay.return_value.task_id = 'fake-id'
            client.post(
                url,
                data=json.dumps({'forceSync': True}),
                content_type='application/json',
            )
        mock_task.delay.assert_called_once()
        _, kwargs = mock_task.delay.call_args
        assert kwargs['force_sync_all_data'] is True


@pytest.mark.django_db
class TestRunMultiExportHtmxBranch:
    def test_htmx_request_returns_204(self, client, multi_export_config):
        url = reverse('exports:run_multi_export', args=[multi_export_config.id])
        response = client.post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    def test_htmx_request_creates_multi_export_run(
        self, client, multi_export_config
    ):
        url = reverse('exports:run_multi_export', args=[multi_export_config.id])
        client.post(url, HTTP_HX_REQUEST='true')
        assert MultiProjectExportRun.objects.filter(
            base_export_config=multi_export_config,
            triggered_from_ui=True,
        ).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest apps/exports/tests/test_list_view.py::TestRunExportHtmxBranch apps/exports/tests/test_list_view.py::TestRunMultiExportHtmxBranch -v --no-migrations
```

Expected: FAIL — `json.decoder.JSONDecodeError` for HTMX tests, or wrong status code

- [ ] **Step 3: Update `run_export` in `apps/exports/views.py`**

Replace the current `run_export` body (lines ~465-480):

```python
@login_required
@require_POST
def run_export(request, export_id):
    export = get_object_or_404(ExportConfig, id=export_id)

    if request.headers.get('HX-Request'):
        force_sync = False
    else:
        options = json.loads(request.body)
        force_sync = options.get('forceSync', False)

    export_record = ExportRun.objects.create(
        base_export_config=export,
        export_config_version=export.latest_version,
        triggered_from_ui=True,
        triggered_by=request.user,
    )

    result = run_export_task.delay(
        export_record.id, force_sync_all_data=force_sync
    )
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)
    return HttpResponse(result.task_id)
```

Replace `run_multi_export` similarly (lines ~483-501). Note it uses `MultiProjectExportRun.objects.create(...)` and `run_multi_project_export_task.delay(...)` — preserve both:

```python
@login_required
@require_POST
def run_multi_export(request, export_id):
    export = get_object_or_404(MultiProjectExportConfig, id=export_id)

    if request.headers.get('HX-Request'):
        force_sync = False
    else:
        options = json.loads(request.body)
        force_sync = options.get('forceSync', False)

    export_record = MultiProjectExportRun.objects.create(
        base_export_config=export,
        export_config_version=export.latest_version,
        triggered_from_ui=True,
        triggered_by=request.user,
    )

    result = run_multi_project_export_task.delay(
        export_record.id,
        force_sync_all_data=force_sync,
    )
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)
    return HttpResponse(result.task_id)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest apps/exports/tests/test_list_view.py::TestRunExportHtmxBranch apps/exports/tests/test_list_view.py::TestRunMultiExportHtmxBranch -v --no-migrations
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/exports/views.py apps/exports/tests/test_list_view.py
git commit -m "feat: add HTMX branch to run_export and run_multi_export (returns 204)"
```

---

## Task 6: HTMX branch in `run_refresh` and `run_forwarding`

**Files:**
- Modify: `apps/refreshes/views.py:273-287`
- Modify: `apps/forwarding/views.py:404-418`
- Test: `apps/refreshes/tests/test_views.py`, `apps/forwarding/tests/test_views.py`

- [ ] **Step 1: Write the failing tests**

In `apps/refreshes/tests/test_views.py`, add:

```python
@pytest.mark.django_db
class TestRunRefreshHtmxBranch:
    def test_htmx_request_returns_204(self, client, refresh_config):
        # client fixture in conftest.py is already logged in
        url = reverse('refreshes:run_refresh', args=[refresh_config.id])
        response = client.post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    def test_htmx_request_creates_refresh_run(self, client, refresh_config):
        from apps.refreshes.models import RefreshRun
        url = reverse('refreshes:run_refresh', args=[refresh_config.id])
        client.post(url, HTTP_HX_REQUEST='true')
        assert RefreshRun.objects.filter(
            refresh_config=refresh_config,
            triggered_from_ui=True,
        ).exists()

    def test_non_htmx_request_returns_200(self, client, refresh_config):
        url = reverse('refreshes:run_refresh', args=[refresh_config.id])
        response = client.post(url)
        assert response.status_code == 200
        assert len(response.content) > 0
```

In `apps/forwarding/tests/test_views.py`, first add a `forwarding_config` fixture near the top of the file alongside the existing `destination` and `database` fixtures:

```python
@pytest.fixture
def forwarding_config(db, database, destination):
    return ForwardingConfig.objects.create(
        name='Test Config',
        database=database,
        destination=destination,
        query='SELECT 1',
    )
```

Then add the test class. Use `regular_client` (already defined in the file) — `run_forwarding` is `@login_required`, not admin-only:

```python
@pytest.mark.django_db
class TestRunForwardingHtmxBranch:
    def test_htmx_request_returns_204(self, regular_client, forwarding_config):
        url = reverse('forwarding:run_forwarding', args=[forwarding_config.id])
        response = regular_client.post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    def test_htmx_request_creates_forwarding_run(
        self, regular_client, forwarding_config
    ):
        url = reverse('forwarding:run_forwarding', args=[forwarding_config.id])
        regular_client.post(url, HTTP_HX_REQUEST='true')
        assert ForwardingRun.objects.filter(
            forwarding_config=forwarding_config,
            triggered_from_ui=True,
        ).exists()

    def test_non_htmx_request_returns_200(
        self, regular_client, forwarding_config
    ):
        url = reverse('forwarding:run_forwarding', args=[forwarding_config.id])
        response = regular_client.post(url)
        assert response.status_code == 200
        assert len(response.content) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest apps/refreshes/tests/test_views.py::TestRunRefreshHtmxBranch apps/forwarding/tests/test_views.py::TestRunForwardingHtmxBranch -v --no-migrations
```

Expected: FAIL — wrong status code

- [ ] **Step 3: Update `run_refresh` in `apps/refreshes/views.py`**

```python
@login_required
@require_POST
def run_refresh(request, config_id):
    """Manually trigger a refresh run."""
    config = get_object_or_404(RefreshConfig, id=config_id)

    refresh_run = RefreshRun.objects.create(
        refresh_config=config,
        refresh_config_version=config.latest_version,
        triggered_from_ui=True,
        triggered_by=request.user,
    )

    result = run_refresh_task.delay(refresh_run.id)
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)
    return HttpResponse(result.task_id)
```

Update `run_forwarding` in `apps/forwarding/views.py` (same pattern — it already doesn't parse JSON, just add the 204 branch):

```python
@login_required
@require_POST
def run_forwarding(request, forwarder_id):
    """Manually trigger a forwarding run."""
    forwarder = get_object_or_404(ForwardingConfig, id=forwarder_id)

    forwarding_run = ForwardingRun.objects.create(
        forwarding_config=forwarder,
        forwarding_config_version=forwarder.latest_version,
        triggered_from_ui=True,
        triggered_by=request.user,
    )

    result = run_forwarding_task.delay(forwarding_run.id)
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)
    return HttpResponse(result.task_id)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest apps/refreshes/tests/test_views.py::TestRunRefreshHtmxBranch apps/forwarding/tests/test_views.py::TestRunForwardingHtmxBranch -v --no-migrations
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/refreshes/views.py apps/refreshes/tests/test_views.py \
        apps/forwarding/views.py apps/forwarding/tests/test_views.py
git commit -m "feat: add HTMX branch to run_refresh and run_forwarding (returns 204)"
```

---

## Task 7: Template rendering tests for Run button (all three apps)

These tests verify the server-rendered HTML before templates are updated (they will fail), then pass after Task 8.

**Files:**
- Test: `apps/exports/tests/test_list_view.py`
- Test: `apps/refreshes/tests/test_views.py`
- Test: `apps/forwarding/tests/test_views.py`

- [ ] **Step 1: Write the failing template tests**

In `apps/exports/tests/test_list_view.py`, add:

```python
@pytest.mark.django_db
class TestExportsRunButtonRendering:
    def test_run_button_present_when_no_active_run(
        self, client, export_config
    ):
        url = reverse('exports:config_table')
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        run_url = reverse('exports:run_export', args=[export_config.id])
        assert f'hx-post="{run_url}"' in content

    def test_run_button_disabled_when_active_run(self, client, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.QUEUED,
        )
        url = reverse('exports:config_table')
        response = client.get(url)
        content = response.content.decode()
        # Run button present but disabled
        assert 'btn-outline-success' in content
        run_url = reverse('exports:run_export', args=[export_config.id])
        assert f'hx-post="{run_url}"' not in content  # disabled, no hx-post

    def test_multi_export_run_button_uses_multi_url(
        self, client, multi_export_config
    ):
        url = reverse('exports:config_table')
        response = client.get(url)
        content = response.content.decode()
        run_url = reverse(
            'exports:run_multi_export', args=[multi_export_config.id]
        )
        assert f'hx-post="{run_url}"' in content

    def test_edit_button_never_disabled(self, client, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.QUEUED,
        )
        url = reverse('exports:config_table')
        response = client.get(url)
        content = response.content.decode()
        edit_url = export_config.edit_url
        assert edit_url in content
```

Add similar classes `TestRefreshesRunButtonRendering` in `apps/refreshes/tests/test_views.py` and `TestForwardingRunButtonRendering` in `apps/forwarding/tests/test_views.py`, adapted to the appropriate URL names and models.

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest apps/exports/tests/test_list_view.py::TestExportsRunButtonRendering -v --no-migrations
```

Expected: FAIL — no `hx-post` in rendered HTML yet

- [ ] **Step 3: (No implementation yet — proceed to Task 8)**

---

## Task 8: Update `templates/exports/partials/config_table.html`

**Files:**
- Modify: `templates/exports/partials/config_table.html`

The template currently has `<tbody x-data="{logOpen: false}">`. The Actions `<td>` has Log and Edit — no Run button.

- [ ] **Step 1: Merge `running` into `<tbody x-data>`**

Change line 25:

```html
{# Before #}
<tbody x-data="{logOpen: false}">

{# After #}
<tbody x-data="{logOpen: false, running: false}">
```

- [ ] **Step 2: Add spinner branch to the Status `<td>` (lines 50-57)**

Replace the Status `<td>`:

```html
<td>
  <template x-if="!running">
    {% if config.last_run %}
      <div>{{ config.last_run.status|to_status_icon }} {{ config.last_run.status }}</div>
      <div class="text-muted small">{{ config.last_run.duration|readable_timedelta_short }}</div>
    {% else %}
      <span class="text-muted">—</span>
    {% endif %}
  </template>
  <template x-if="running">
    <span class="d-inline-flex align-items-center gap-1 text-primary small">
      <span class="spinner-border spinner-border-sm"
            style="width:0.8em;height:0.8em"
            role="status"></span>
      {% trans "Running…" %}
    </span>
  </template>
</td>
```

- [ ] **Step 3: Add Run button to the Actions `<td>` (line 58)**

Replace the opening of the Actions `<td>` (before the existing Log conditional). The full `<td class="text-nowrap">` block becomes:

```html
<td class="text-nowrap">
  {% if config.has_active_run %}
    <button class="btn btn-sm btn-outline-success" disabled
            title="{% trans 'Already running' %}">▶ {% trans "Run" %}</button>
  {% else %}
    {% if config.is_multi_project %}
      {% url 'exports:run_multi_export' config.id as run_url %}
    {% else %}
      {% url 'exports:run_export' config.id as run_url %}
    {% endif %}
    <button class="btn btn-sm btn-outline-success"
            :disabled="running"
            @click="running = true"
            hx-post="{{ run_url }}"
            hx-swap="none">▶ {% trans "Run" %}</button>
  {% endif %}

  {% if config.last_run and config.last_run.status == 'completed' or config.last_run and config.last_run.status == 'failed' %}
  <button class="btn btn-outline-secondary btn-sm"
          :class="{'active': logOpen, 'disabled': running}"
          hx-get="{{ config.last_run_log_url }}"
          hx-target="#log-{{ config.id }}"
          hx-trigger="click once"
          @click="logOpen = !logOpen">
    <i class="fa-solid fa-list"></i> {% trans "Log" %}
  </button>
  {% else %}
  <button class="btn btn-outline-secondary btn-sm"
          :class="{'disabled': running}"
          disabled>
    <i class="fa-solid fa-list"></i> {% trans "Log" %}
  </button>
  {% endif %}
  <a href="{{ config.edit_url }}"
     class="btn btn-outline-secondary btn-sm">
    <i class="fa-solid fa-pencil"></i> {% trans "Edit" %}
  </a>
</td>
```

- [ ] **Step 4: Format the template**

```bash
npx prettier --write templates/exports/partials/config_table.html
```

- [ ] **Step 5: Run the template rendering tests**

```bash
uv run pytest apps/exports/tests/test_list_view.py::TestExportsRunButtonRendering -v --no-migrations
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add templates/exports/partials/config_table.html
git commit -m "feat: add Run button to exports config table (with spinner, disabled states)"
```

---

## Task 9: Update `templates/refreshes/partials/config_table.html`

**Files:**
- Modify: `templates/refreshes/partials/config_table.html`

Same changes as Task 8, adapted for refreshes. Key differences:
- `hx-post="{% url 'refreshes:run_refresh' config.id %}"` (no multi-project branch needed)
- Log target `#rlog-{{ config.id }}`, URL `{% url 'refreshes:run_log' config.last_run.id %}`
- No `is_multi_project` conditional

- [ ] **Step 1: Merge `running` into `<tbody x-data>` (line 25)**

```html
<tbody x-data="{logOpen: false, running: false}">
```

- [ ] **Step 2: Add spinner branch to Status `<td>` (lines 50-57)**

Same pattern as Task 8 — wrap existing content in `<template x-if="!running">` and add spinner branch.

- [ ] **Step 3: Add Run button to Actions `<td>` (lines 58-77)**

```html
<td class="text-nowrap">
  {% if config.has_active_run %}
    <button class="btn btn-sm btn-outline-success" disabled
            title="{% trans 'Already running' %}">▶ {% trans "Run" %}</button>
  {% else %}
    <button class="btn btn-sm btn-outline-success"
            :disabled="running"
            @click="running = true"
            hx-post="{% url 'refreshes:run_refresh' config.id %}"
            hx-swap="none">▶ {% trans "Run" %}</button>
  {% endif %}

  {% if config.last_run and config.last_run.status == 'completed' or config.last_run and config.last_run.status == 'failed' %}
  <button class="btn btn-outline-secondary btn-sm"
          :class="{'active': logOpen, 'disabled': running}"
          hx-get="{% url 'refreshes:run_log' config.last_run.id %}"
          hx-target="#rlog-{{ config.id }}"
          hx-trigger="click once"
          @click="logOpen = !logOpen">
    <i class="fa-solid fa-list"></i> {% trans "Log" %}
  </button>
  {% else %}
  <button class="btn btn-outline-secondary btn-sm"
          :class="{'disabled': running}"
          disabled>
    <i class="fa-solid fa-list"></i> {% trans "Log" %}
  </button>
  {% endif %}
  <a href="{% url 'refreshes:edit_refresh_config' config.id %}"
     class="btn btn-outline-secondary btn-sm">
    <i class="fa-solid fa-pencil"></i> {% trans "Edit" %}
  </a>
</td>
```

- [ ] **Step 4: Format**

```bash
npx prettier --write templates/refreshes/partials/config_table.html
```

- [ ] **Step 5: Run the template rendering tests**

```bash
uv run pytest apps/refreshes/tests/test_views.py::TestRefreshesRunButtonRendering -v --no-migrations
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add templates/refreshes/partials/config_table.html
git commit -m "feat: add Run button to refreshes config table (with spinner, disabled states)"
```

---

## Task 10: Update `templates/forwarding/partials/config_table.html`

**Files:**
- Modify: `templates/forwarding/partials/config_table.html`

Same changes as Tasks 8-9, adapted for forwarding. Key differences:
- `hx-post="{% url 'forwarding:run_forwarding' config.id %}"` (URL kwarg is `forwarder_id` but positional `{% url %}` works)
- Log target `#flog-{{ config.id }}`, URL `{% url 'forwarding:run_log' config.last_run.id %}`

- [ ] **Step 1: Merge `running` into `<tbody x-data>` (line 25)**

```html
<tbody x-data="{logOpen: false, running: false}">
```

- [ ] **Step 2: Add spinner branch to Status `<td>` (lines 50-57)**

Same pattern as previous tasks.

- [ ] **Step 3: Add Run button to Actions `<td>` (lines 58-77)**

```html
<td class="text-nowrap">
  {% if config.has_active_run %}
    <button class="btn btn-sm btn-outline-success" disabled
            title="{% trans 'Already running' %}">▶ {% trans "Run" %}</button>
  {% else %}
    <button class="btn btn-sm btn-outline-success"
            :disabled="running"
            @click="running = true"
            hx-post="{% url 'forwarding:run_forwarding' config.id %}"
            hx-swap="none">▶ {% trans "Run" %}</button>
  {% endif %}

  {% if config.last_run and config.last_run.status == 'completed' or config.last_run and config.last_run.status == 'failed' %}
  <button class="btn btn-outline-secondary btn-sm"
          :class="{'active': logOpen, 'disabled': running}"
          hx-get="{% url 'forwarding:run_log' config.last_run.id %}"
          hx-target="#flog-{{ config.id }}"
          hx-trigger="click once"
          @click="logOpen = !logOpen">
    <i class="fa-solid fa-list"></i> {% trans "Log" %}
  </button>
  {% else %}
  <button class="btn btn-outline-secondary btn-sm"
          :class="{'disabled': running}"
          disabled>
    <i class="fa-solid fa-list"></i> {% trans "Log" %}
  </button>
  {% endif %}
  <a href="{% url 'forwarding:edit_forwarding_config' config.id %}"
     class="btn btn-outline-secondary btn-sm">
    <i class="fa-solid fa-pencil"></i> {% trans "Edit" %}
  </a>
</td>
```

- [ ] **Step 4: Format**

```bash
npx prettier --write templates/forwarding/partials/config_table.html
```

- [ ] **Step 5: Run the template rendering tests**

```bash
uv run pytest apps/forwarding/tests/test_views.py::TestForwardingRunButtonRendering -v --no-migrations
```

Expected: PASS

- [ ] **Step 6: Run the full test suite**

```bash
uv run pytest --no-migrations -x -q
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add templates/forwarding/partials/config_table.html
git commit -m "feat: add Run button to forwarding config table (with spinner, disabled states)"
```

---

## Task 11: Playwright test for Run button on exports list page

**Files:**
- Create: `apps/exports/tests/test_list_run_button_playwright.py`

This test uses a live server and real Alpine.js + HTMX. It is separate from the existing `test_run_button_playwright.py` (which tests the **detail page**). Follow the patterns in that file and in `test_export_form_playwright.py`.

- [ ] **Step 1: Read existing Playwright helpers**

Read `apps/exports/tests/helpers.py` and `apps/exports/tests/conftest.py` to understand `login()`, `navigate_to_export_details()`, and Playwright fixture setup before writing tests.

- [ ] **Step 2: Write the Playwright test file**

```python
"""
Playwright tests for Run button on the Exports list page.
"""
import pytest
from playwright.sync_api import expect
from unmagic import get_request

from apps.exports.models import ExportConfig, ExportRun
from .fixtures import test_data
from .helpers import login


def navigate_to_exports_list(page, live_server):
    from django.urls import reverse
    page.goto(f"{live_server.url}{reverse('exports:home')}")


@pytest.mark.django_db(transaction=True)
class TestListPageRunButton:

    def test_run_button_appears_in_actions_column(self):
        page = get_request().getfixturevalue('page')
        live_server = get_request().getfixturevalue('live_server')
        data = test_data()
        ExportConfig.objects.create(
            name='Test Export',
            account=data['account'],
            project=data['project'],
            database=data['database'],
        )
        login(page, live_server, data['user'])
        navigate_to_exports_list(page, live_server)

        run_button = page.locator('button.btn-outline-success').first
        expect(run_button).to_be_visible()
        expect(run_button).to_contain_text('Run')

    def test_clicking_run_shows_spinner_in_status_cell(self):
        """Clicking Run immediately sets running=true via Alpine.js."""
        page = get_request().getfixturevalue('page')
        live_server = get_request().getfixturevalue('live_server')
        data = test_data()
        ExportConfig.objects.create(
            name='Test Export',
            account=data['account'],
            project=data['project'],
            database=data['database'],
        )
        login(page, live_server, data['user'])
        navigate_to_exports_list(page, live_server)

        # Mock the run endpoint to respond quickly
        page.route('**/exports/api/run/**', lambda route: route.fulfill(
            status=204, body=''
        ))

        run_button = page.locator('button.btn-outline-success').first
        run_button.click()

        # Spinner appears immediately (Alpine.js optimistic update)
        spinner = page.locator('.spinner-border').first
        expect(spinner).to_be_visible(timeout=1000)

    def test_clicking_run_disables_run_and_log_buttons(self):
        """After click, Run button is disabled; Edit link is not."""
        page = get_request().getfixturevalue('page')
        live_server = get_request().getfixturevalue('live_server')
        data = test_data()
        ExportConfig.objects.create(
            name='Test Export',
            account=data['account'],
            project=data['project'],
            database=data['database'],
        )
        login(page, live_server, data['user'])
        navigate_to_exports_list(page, live_server)

        page.route('**/exports/api/run/**', lambda route: route.fulfill(
            status=204, body=''
        ))

        run_button = page.locator('button.btn-outline-success').first
        run_button.click()
        page.wait_for_timeout(100)  # let Alpine update

        expect(run_button).to_be_disabled()

        # Edit button remains active
        edit_link = page.locator('a.btn-outline-secondary:has-text("Edit")').first
        expect(edit_link).not_to_have_attribute('disabled', '')

    def test_htmx_poll_resets_running_state(self):
        """Triggering the HTMX poll resets Alpine running state."""
        page = get_request().getfixturevalue('page')
        live_server = get_request().getfixturevalue('live_server')
        data = test_data()
        ExportConfig.objects.create(
            name='Test Export',
            account=data['account'],
            project=data['project'],
            database=data['database'],
        )
        login(page, live_server, data['user'])
        navigate_to_exports_list(page, live_server)

        page.route('**/exports/api/run/**', lambda route: route.fulfill(
            status=204, body=''
        ))

        run_button = page.locator('button.btn-outline-success').first
        run_button.click()
        page.wait_for_timeout(100)

        expect(run_button).to_be_disabled()

        # Trigger the HTMX poll manually (fires the same "every 60s" event)
        page.evaluate(
            "htmx.trigger(document.getElementById('exports-config-table'), 'every 60s')"
        )
        page.wait_for_timeout(500)  # allow HTMX response + Alpine reset

        # Row now reflects server state; Run button should be re-enabled
        # (the export has no active run server-side)
        expect(run_button).not_to_be_disabled(timeout=2000)
```

- [ ] **Step 3: Run the Playwright tests**

```bash
uv run pytest apps/exports/tests/test_list_run_button_playwright.py -v
```

Expected: PASS (all four tests)

- [ ] **Step 4: Run the full test suite one final time**

```bash
uv run pytest --no-migrations -x -q
```

Expected: all tests pass, none failing

- [ ] **Step 5: Commit**

```bash
git add apps/exports/tests/test_list_run_button_playwright.py
git commit -m "test: Playwright tests for Run button on exports list page"
```
