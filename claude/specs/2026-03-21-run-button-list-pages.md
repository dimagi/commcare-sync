# Run Button on List Pages — Design Spec

## Goal

Add a "▶ Run" button to the Actions column on the Exports, Refreshes, and
Forwarders list pages, with inline per-row progress feedback while the run
is in progress.

---

## User Experience

### Button placement

Actions column order: **▶ Run · 📋 Log · ✏ Edit** (Run is leftmost).

### Row states

| State                             | Status cell                             | Run button                    | Log button                                     | Edit button |
|-----------------------------------|-----------------------------------------|-------------------------------|------------------------------------------------|-------------|
| Normal                            | Existing badge (Completed / Failed / —) | Active, `btn-outline-success` | Active if last_run has completed/failed status | Active      |
| Running (optimistic)              | Spinner + "Running…"                    | Disabled (HTML attribute)     | Disabled                                       | Active      |
| Already queued / started (server) | Previous badge or —                     | Disabled (server-rendered)    | Unchanged (existing server-side logic)         | Active      |

**Notes on the "already queued/started" state:**

- `last_run` on all three config model families explicitly excludes QUEUED
  runs (filters them out in Python from `_all_runs`). So when a run is
  QUEUED, the Status cell will show whatever the previous
  completed/failed badge was, or `—` if there is no previous run. The
  spec does not require changing the Status cell in this state — disabled
  Run button is sufficient.
- The Log button is already conditionally active or disabled by the
  existing server-side template logic (active only when `config.last_run`
  exists and has `completed` or `failed` status). That existing logic
  stays untouched. The **only** client-side addition is: when `running=true`,
  also show Log as disabled (there is no new completed run to view yet).

### Always normal run

The Run button always triggers a normal (non-force) run (`forceSync: false`),
identical to clicking Run on the detail page without the Force checkbox.

---

## Architecture

Three layers cooperate:

1. **Alpine.js optimistic UI** — `running: false` is merged into the
   existing `<tbody x-data="{logOpen: false, running: false}">` (all three
   partials already have a `<tbody x-data>`). A click handler sets
   `running = true`; the Status cell conditionally renders the spinner;
   Run uses Alpine's `:disabled="running"` (the real HTML attribute, not
   just CSS) so browser click-suppression and HTMX both honour it.

   The `<tbody>` wraps two `<tr>` elements: the main data row and the
   collapsible log row (`x-show="logOpen"`). The `running` variable is
   visible in both rows' scope. Since the log row uses only `logOpen` for
   its visibility, `running` does not affect it.

2. **HTMX** — the Run button carries `hx-post` with `hx-swap="none"`
   (response body is discarded). Alpine's `@click` sets the optimistic
   state before the POST fires. Because the button uses `:disabled="running"`,
   a second click while running cannot trigger another POST. CSRF is
   handled automatically by the existing project HTMX setup (HTMX sends
   the `X-CSRFToken` header via the meta tag on every POST; no extra work
   needed).

3. **60-second HTMX poll** — already present on all three list pages
   (`hx-trigger="every 60s"`, `hx-swap="outerHTML"` on the outer
   container). When it refreshes the `<div>` via `outerHTML`, the DOM is
   replaced and Alpine state resets naturally, showing the authoritative
   server-rendered status.

---

## Backend changes

### 1. `is_multi_project` property on `ExportConfigBase`

The exports config table renders both `ExportConfig` and
`MultiProjectExportConfig` objects in the same loop. They require
different run URL names. Add a distinguishing boolean property to the
shared abstract base:

```python
# ExportConfigBase
@property
def is_multi_project(self):
    return False

# MultiProjectExportConfig (override)
@property
def is_multi_project(self):
    return True
```

### 2. `has_active_run` property

**Exports** — add to `ExportConfigBase` (both concrete classes inherit
it). Uses `ExportRun.Status`, which is defined on `ExportRunBase` and
accessible on `ExportRun`. The prefetch attribute name is `_all_runs`
(set by the list view's `prefetch_related(..., to_attr='_all_runs')`):

```python
# ExportConfigBase
@property
def has_active_run(self):
    active = {ExportRun.Status.QUEUED, ExportRun.Status.STARTED}
    all_runs = getattr(self, '_all_runs', None)
    if all_runs is not None:
        return any(r.status in active for r in all_runs)
    return self.runs.filter(status__in=active).exists()
```

**Refreshes** — add to `RefreshConfig`. `RefreshRun` inherits `Status`
from `RunBaseModel` (it does not define its own `Status` inner class);
`RefreshRun.Status.QUEUED` resolves via Python's MRO:

```python
# RefreshConfig
@property
def has_active_run(self):
    active = {RefreshRun.Status.QUEUED, RefreshRun.Status.STARTED}
    all_runs = getattr(self, '_all_runs', None)
    if all_runs is not None:
        return any(r.status in active for r in all_runs)
    return self.runs.filter(status__in=active).exists()
```

**Forwarding** — same pattern on `ForwardingConfig`. `ForwardingRun.Status`
likewise inherits from `RunBaseModel.Status`:

```python
# ForwardingConfig
@property
def has_active_run(self):
    active = {ForwardingRun.Status.QUEUED, ForwardingRun.Status.STARTED}
    all_runs = getattr(self, '_all_runs', None)
    if all_runs is not None:
        return any(r.status in active for r in all_runs)
    return self.runs.filter(status__in=active).exists()
```

### 3. Run views — handle HTMX requests

`run_export` and `run_multi_export` call `json.loads(request.body)` before
anything else. An HTMX `hx-post` sends `application/x-www-form-urlencoded`
(the CSRF token field), which is not valid JSON — the parse raises
`JSONDecodeError`. Fix: branch on `HX-Request` header so HTMX calls skip
the JSON parse and always use `force_sync=False`. Return `204 No Content`
(the list page discards the response body).

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
    result = run_export_task.delay(export_record.id, force_sync_all_data=force_sync)
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)
    return HttpResponse(result.task_id)
```

Apply the same HTMX branch to `run_multi_export` (which creates
`MultiProjectExportRun.objects.create(...)` and calls
`run_multi_project_export_task.delay(...)` — preserve both, only add the
branch) and `run_refresh`. For `run_forwarding`, only the 204 return
branch is needed (it does not parse a JSON body today):

```python
    result = run_forwarding_task.delay(...)
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)
    return HttpResponse(result.task_id)
```

---

## Template changes

### Affected files

| App        | Partial                                           |
|------------|---------------------------------------------------|
| Exports    | `templates/exports/partials/config_table.html`    |
| Refreshes  | `templates/refreshes/partials/config_table.html`  |
| Forwarding | `templates/forwarding/partials/config_table.html` |

### `<tbody>` x-data — merge `running` into existing scope

All three partials already have:

```html
<tbody x-data="{logOpen: false}">
```

Change to:

```html
<tbody x-data="{logOpen: false, running: false}">
```

Do **not** add a separate `x-data` on `<tr>`. Verify the log row
(`x-show="logOpen"`) is unaffected by `running` — it only references
`logOpen`, which is unchanged.

### Status cell — add spinner branch

Wrap the existing status content in a conditional Alpine block and add a
spinner branch. Example (adapt to each partial's actual markup):

```html
<td>
  <template x-if="!running">
    {# existing status badge / dash — unchanged #}
  </template>
  <template x-if="running">
    <span class="d-inline-flex align-items-center gap-1 text-primary small">
      <span class="spinner-border spinner-border-sm"
            style="width:0.8em;height:0.8em"
            role="status"></span>
      Running…
    </span>
  </template>
</td>
```

### Actions cell — Run · Log · Edit

**Key rules:**
- Run button is a `<button>` with `:disabled="running"` (real attribute,
  not CSS class only).
- Log button is a `<button>` per the existing markup (not `<a>`). The
  existing server-rendered active/disabled conditional logic (`{% if config.last_run and ... %}`) is **preserved unchanged**. Add `:class="{ disabled: running }"` to both the active and disabled Log `<button>` variants.
- Edit link stays as-is.

**Exports** (the loop renders both `ExportConfig` and
`MultiProjectExportConfig` objects; use `config.is_multi_project` added
in step 1 to select the correct run URL):

```html
{% if config.has_active_run %}
  <button class="btn btn-sm btn-outline-success" disabled
          title="Already running">▶ Run</button>
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
          hx-swap="none">▶ Run</button>
{% endif %}

{# Log — existing conditional preserved; Alpine adds running-state disable #}
{% if config.last_run and config.last_run.status == 'completed' or config.last_run and config.last_run.status == 'failed' %}
<button class="btn btn-outline-secondary btn-sm"
        :class="{'active': logOpen, 'disabled': running}"
        hx-get="{{ config.last_run_log_url }}"
        hx-target="#log-{{ config.id }}"
        hx-trigger="click once"
        @click="logOpen = !logOpen">
  <i class="fa-solid fa-list"></i> Log
</button>
{% else %}
<button class="btn btn-outline-secondary btn-sm"
        :class="{'disabled': running}"
        disabled>
  <i class="fa-solid fa-list"></i> Log
</button>
{% endif %}

{# Edit — unchanged #}
```

**Refreshes** and **Forwarding**: identical structure with a single run
URL per app (no `is_multi_project` conditional needed). Use positional
`{% url %}` syntax — the URL kwarg names differ from exports
(`config_id` for refresh, `forwarder_id` for forwarding) but positional
resolution works:

```html
{# Refreshes #}
<button ... hx-post="{% url 'refreshes:run_refresh' config.id %}" hx-swap="none">▶ Run</button>

{# Forwarding #}
<button ... hx-post="{% url 'forwarding:run_forwarding' config.id %}" hx-swap="none">▶ Run</button>
```

---

## Scope

**In scope:**
- Single-project exports (`ExportConfig`)
- Multi-project exports (`MultiProjectExportConfig`)
- Refreshes (`RefreshConfig`)
- Forwarding configs (`ForwardingConfig`)

**Out of scope:**
- Cancel button
- Progress percentage / Celery progress polling on the list page
- Automatic redirect to detail page after run completes

---

## Testing

### Unit tests — `is_multi_project` property

- `ExportConfig.is_multi_project` returns `False`
- `MultiProjectExportConfig.is_multi_project` returns `True`

### Unit tests — `has_active_run` property

One test class per model (`ExportConfig`, `RefreshConfig`,
`ForwardingConfig`). For each:

- Returns `False` when there are no runs
- Returns `False` when the only run is Completed
- Returns `False` when the only run is Failed
- Returns `True` when a run has status QUEUED
- Returns `True` when a run has status STARTED
- Prefetch path: set `config._all_runs = [run_instance]` directly on the
  instance and assert the property returns the correct result without
  hitting the database. Use the `TestCase.assertNumQueries` context
  manager:
  ```python
  with self.assertNumQueries(0):
      result = config.has_active_run
  assert result is True
  ```

### Unit tests — run view HTMX branch

For each of the four views (`run_export`, `run_multi_export`,
`run_refresh`, `run_forwarding`):

- HTMX request (`HTTP_HX_REQUEST=true` on test client) → status 204
- HTMX request → a run record is created with `triggered_from_ui=True`
  and the correct config (`ExportRun` for `run_export`,
  `MultiProjectExportRun` for `run_multi_export`, `RefreshRun` for
  `run_refresh`, `ForwardingRun` for `run_forwarding`)
- Non-HTMX request → status 200, body equals the Celery task ID
  (existing behaviour unchanged)

For `run_export` and `run_multi_export` only:

- Non-HTMX request with `{"forceSync": true}` JSON body → task called
  with `force_sync_all_data=True`

### Template rendering tests — list views

For each of the three apps (using `Client.get` on the list URL):

- When `has_active_run` is `False`: Run button rendered, no `disabled`
  attribute, correct `hx-post` URL
- When `has_active_run` is `True`: Run button rendered with `disabled`
  attribute
- Edit link never has `disabled`

For the exports list specifically:

- A single-project config row has `hx-post` pointing to
  `exports:run_export`
- A multi-project config row has `hx-post` pointing to
  `exports:run_multi_export`

### Playwright test (exports, one app is sufficient)

1. Navigate to the Exports list page
2. Click ▶ Run on a config that has no active run
3. Assert the Status cell now contains a spinner element (immediately,
   before any poll)
4. Assert the Run button has the `disabled` attribute
5. Assert the Log button has CSS class `disabled`
6. Assert the Edit link is active (no `disabled`)
7. Trigger the HTMX poll manually via:
   ```javascript
   htmx.trigger(document.getElementById('exports-config-table'), 'every 60s')
   ```
   This fires the same polling trigger that normally fires every 60 seconds
   (`hx-trigger="every 60s"` on `<div id="exports-config-table">`). Assert
   the row returns to its normal state (spinner gone, Run button re-enabled).
   Follow the established project Playwright pattern used in
   `apps/exports/tests/test_export_form_playwright.py`.
