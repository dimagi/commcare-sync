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

| State | Status cell | Run button | Log button | Edit button |
|---|---|---|---|---|
| Normal | Existing badge (Completed / Failed / —) | Active, `btn-outline-success` | Active | Active |
| Running (optimistic) | Spinner + "Running…" | Disabled (HTML attribute) | Disabled | Active |
| Already queued / started (server) | Existing badge or — | Disabled (server-rendered) | Active | Active |

**Notes on the "already queued/started" state:**

- `last_run` on all three config model families explicitly excludes QUEUED
  runs (filters them out in Python from `_all_runs`). So when a run is
  QUEUED, the Status cell will show whatever the previous completed/failed
  badge was, or `—` if there is no previous run. The spec does not require
  changing the Status cell in this state — disabled Run button is
  sufficient.
- Log remains active in this state (the user can still view logs of a
  previous completed run). Log is only disabled in the **running
  (optimistic)** state because there is no new completed run to show yet.

### Always normal run

The Run button always triggers a normal (non-force) run, identical to
clicking Run on the detail page without the "Force" checkbox checked.
`forceSync` is always `false`.

---

## Architecture

Three layers cooperate:

1. **Alpine.js optimistic UI** — `running: false` is merged into the
   existing `<tbody x-data="{logOpen: false, running: false}">` (all three
   partials already have a `<tbody x-data>`). A click handler sets
   `running = true`; the Status cell conditionally renders the spinner;
   Run and Log buttons use Alpine's `:disabled="running"` (the real HTML
   attribute, not just a CSS class) so browser click-suppression and HTMX
   both respect the disabled state.

2. **HTMX** — the Run button carries `hx-post` to the existing run
   endpoint with `hx-swap="none"` (response body is discarded). Alpine's
   `@click` sets the optimistic state before the POST fires. Because the
   button uses `:disabled="running"`, a second click while running cannot
   trigger another POST.

3. **60-second HTMX poll** — already present on all three list pages.
   When it refreshes the `<tbody>` via `outerHTML`, the server-rendered
   HTML replaces the DOM, naturally resetting Alpine state and showing the
   authoritative status.

---

## Backend changes

### 1. Run views — handle HTMX requests

`run_export` and `run_multi_export` currently do `json.loads(request.body)`.
An HTMX `hx-post` sends `application/x-www-form-urlencoded` (the CSRF
token), not JSON, so the parse will raise `JSONDecodeError`.

Fix: branch on `HX-Request` header. For HTMX calls, `forceSync` is
always `false` (list page never force-runs). Return `HttpResponse(status=204)`
instead of the task-ID body (the list page discards the body).

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

Apply the identical pattern to `run_multi_export` and `run_refresh`.

`run_forwarding` does not parse a JSON body today, so only the 204 branch
needs adding there:

```python
    result = run_forwarding_task.delay(...)
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)
    return HttpResponse(result.task_id)
```

### 2. `has_active_run` property on config models

Add to `ExportConfig`, `MultiProjectExportConfig`, `RefreshConfig`, and
`ForwardingConfig`. Use the prefetched `_all_runs` list when available to
avoid N+1 queries (the list views already prefetch runs with
`to_attr='_all_runs'`).

For **`ExportConfig`** and **`MultiProjectExportConfig`**:

```python
@property
def has_active_run(self):
    active = {ExportRun.Status.QUEUED, ExportRun.Status.STARTED}
    all_runs = getattr(self, '_all_runs', None)
    if all_runs is not None:
        return any(r.status in active for r in all_runs)
    return self.runs.filter(status__in=active).exists()
```

For **`RefreshConfig`**:

```python
@property
def has_active_run(self):
    active = {RefreshRun.Status.QUEUED, RefreshRun.Status.STARTED}
    all_runs = getattr(self, '_all_runs', None)
    if all_runs is not None:
        return any(r.status in active for r in all_runs)
    return self.runs.filter(status__in=active).exists()
```

For **`ForwardingConfig`**:

```python
@property
def has_active_run(self):
    active = {ForwardingRun.Status.QUEUED, ForwardingRun.Status.STARTED}
    all_runs = getattr(self, '_all_runs', None)
    if all_runs is not None:
        return any(r.status in active for r in all_runs)
    return self.runs.filter(status__in=active).exists()
```

---

## Template changes

### Affected files

All three apps use config-table partials (not top-level list templates).
These partials are what the HTMX 60-second poll replaces via `outerHTML`:

| App | Partial |
|---|---|
| Exports | `templates/exports/partials/config_table.html` |
| Refreshes | `templates/refreshes/partials/config_table.html` |
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

Do **not** add a separate `x-data` on `<tr>`.

### Status cell — add spinner branch

Wrap the existing status badge in a conditional Alpine block and add a
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

**Exports** (handles both `ExportConfig` and `MultiProjectExportConfig`;
the URL name differs per type — `exports:run_export` vs
`exports:run_multi_export` — and the config object has an
`is_multi_project` distinguishing property or can be type-checked):

```html
<td>
  {% if config.has_active_run %}
    <button class="btn btn-sm btn-outline-success"
            disabled
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

  <a class="btn btn-sm btn-outline-secondary"
     :class="{ disabled: running }"
     href="...">📋 Log</a>

  <a class="btn btn-sm btn-outline-secondary"
     href="...">✏ Edit</a>
</td>
```

> Note: The exports config table already renders both single and
> multi-project configs in a single loop. The implementer must inspect
> the template to determine how config type is distinguished (e.g., a
> `config.is_multi_project` boolean property, or `{% if config|is_instance:"MultiProjectExportConfig" %}`).

> Use `:disabled="running"` (Alpine binding → real HTML `disabled`
> attribute) not just `:class="{ disabled: running }"` (CSS only). The
> real attribute suppresses browser click events and therefore prevents
> HTMX from firing a second POST.

**Refreshes** and **Forwarding**: same structure, substituting the
appropriate `{% url %}` tag (`refreshes:run_refresh` /
`forwarding:run_forwarding`). These apps have only one config type each.

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

### Unit tests — `has_active_run` property

Write one test class per model (four total). For each:

- Returns `False` when there are no runs
- Returns `False` when all runs are Completed or Failed
- Returns `True` when a run has status QUEUED
- Returns `True` when a run has status STARTED
- Returns `True` (prefetch path): set `config._all_runs = [run_object]`
  directly on the instance and assert the property uses it without hitting
  the database (wrap in `assertNumQueries(0)`)

### Unit tests — run view HTMX branch

For `run_export`, `run_multi_export`, `run_refresh`, `run_forwarding`:

- HTMX request (pass `HTTP_HX_REQUEST=true` to test client) → status 204
- HTMX request → run record created with correct config and
  `triggered_from_ui=True`
- Non-HTMX request → status 200, body is the task ID (existing behaviour
  unchanged)

For `run_export` and `run_multi_export` only:

- Non-HTMX request with `{"forceSync": true}` JSON body → task called
  with `force_sync_all_data=True`

### Template rendering tests — list views

For each of the three list views (`Client.get`):

- Run button is present and **not** disabled when `has_active_run` is `False`
- Run button has `disabled` attribute when `has_active_run` is `True`
- Log button has CSS class `disabled` when running optimistically (Alpine)
  — since this is server-rendered test, check the `has_active_run=True`
  case does NOT add disabled to Log (Log is only disabled client-side)
- Edit link is always rendered without `disabled`
- `hx-post` attribute on Run button points to the correct URL

### Playwright test (one app, exports)

1. Navigate to the Exports list page
2. Click ▶ Run on a config that has no active run
3. Assert the Status cell now contains a spinner element immediately
   (before any poll)
4. Assert the Run button is disabled
5. Assert the Log button has CSS class `disabled`
6. Assert the Edit link is still active
7. Trigger the HTMX poll with `page.evaluate("htmx.trigger(...)")` using
   the trigger event name on the config table container, and assert the
   row returns to its normal state (per the project's established Playwright
   pattern — do not wait for the real 60-second interval)
