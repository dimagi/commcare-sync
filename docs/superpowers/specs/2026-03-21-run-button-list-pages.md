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
| Normal | Existing badge (Completed / Failed / —) | Active, outline-success | Active | Active |
| Running (optimistic) | Spinner + mini progress bar + "Running…" | Disabled | Disabled | Active |
| Already queued / started (server) | Existing badge | Disabled (server-rendered) | Disabled | Active |

The **running state** is set optimistically by Alpine.js at click time. The
existing 60-second HTMX poll refreshes the row from the server, picking up
the final Completed/Failed state and resetting the Alpine state.

Log is disabled while running because there is no completed run to show.
Edit remains active so users can navigate to the config while a run is in
progress.

### Always normal run

The Run button always triggers a normal (non-force) run, identical to
clicking Run on the detail page without the "Force" checkbox checked.

---

## Architecture

Three layers cooperate:

1. **Alpine.js** — optimistic per-row state (`x-data="{ running: false }"`).
   Click sets `running = true`; the Status cell conditionally renders the
   spinner; Run and Log buttons use `:disabled` / CSS disabled class.

2. **HTMX** — the Run button fires `hx-post` to the existing run endpoint
   with `hx-swap="none"` (response body is ignored). A `@click` Alpine
   handler sets the optimistic state before the POST fires.

3. **60-second HTMX poll** — already present on all three list pages.
   When it refreshes the row, the server-rendered HTML replaces the DOM,
   naturally resetting Alpine state and showing the authoritative status.

---

## Backend changes

### 1. `has_active_run` property on config models

Add to `ExportConfig`, `MultiProjectExportConfig`, `RefreshConfig`, and
`ForwardingConfig`:

```python
@property
def has_active_run(self):
    return self.runs.filter(
        status__in=[Run.Status.QUEUED, Run.Status.STARTED]
    ).exists()
```

The reverse accessor name (`runs`) follows the existing pattern on each
model. The property is used in templates to server-render the Run button
as disabled when a run is already in flight.

### 2. Run endpoints — HTMX response

The three existing run views (`run_export`, `run_refresh`, `run_forwarding`)
currently redirect to the detail page after queuing the Celery task. Add a
branch: if the request carries the `HX-Request` header, return
`HttpResponse(status=204)` instead of redirecting.

```python
if request.headers.get('HX-Request'):
    return HttpResponse(status=204)
return redirect('exports:export_detail', config_id)
```

No new URLs are needed.

---

## Template changes

### Affected templates

| App | Template |
|---|---|
| Exports | `templates/exports/list.html` |
| Refreshes | `templates/refreshes/list.html` |
| Forwarding | `templates/forwarding/configs.html` |

### Row structure (illustrative — adapt to each template's actual markup)

Add `x-data="{ running: false }"` to the `<tr>`:

```html
<tr x-data="{ running: false }">
```

Status cell — wrap existing badge in a conditional, add spinner branch:

```html
<td>
  <template x-if="!running">
    {# existing status badge unchanged #}
  </template>
  <template x-if="running">
    <span class="d-inline-flex align-items-center gap-1 text-primary small">
      <span class="spinner-border spinner-border-sm" style="width:0.8em;height:0.8em"></span>
      Running…
    </span>
  </template>
</td>
```

Actions cell — Run button first, then Log, then Edit:

```html
<td>
  {% if config.has_active_run %}
    <button class="btn btn-sm btn-outline-success disabled"
            aria-disabled="true"
            title="Already running">▶ Run</button>
  {% else %}
    <button class="btn btn-sm btn-outline-success"
            :class="{ disabled: running }"
            :aria-disabled="running"
            @click="running = true"
            hx-post="{% url 'exports:run_export' config.id %}"
            hx-swap="none">▶ Run</button>
  {% endif %}

  {# Log — also disabled while running #}
  <a class="btn btn-sm btn-outline-secondary {% if config.has_active_run %}disabled{% endif %}"
     :class="{ disabled: running }"
     href="...">📋 Log</a>

  <a class="btn btn-sm btn-outline-secondary" href="...">✏ Edit</a>
</td>
```

> `has_active_run` controls the server-rendered disabled state (already-queued
> rows). Alpine's `running` flag controls the client-side optimistic state
> after the user clicks.

---

## Scope

**In scope:**
- Single-project exports (`ExportConfig`)
- Multi-project exports (`MultiProjectExportConfig`)
- Refreshes (`RefreshConfig`)
- Forwarding configs (`ForwardingConfig`)

**Out of scope:**
- Cancel button (not requested)
- Progress percentage (spinner only, no celery-progress polling on list page)
- Automatic redirect to detail page after run completes

---

## Testing

### Unit tests

**`has_active_run` property** (per model):
- Returns `False` when there are no runs
- Returns `False` when the latest run is Completed or Failed
- Returns `True` when a run is QUEUED
- Returns `True` when a run is STARTED

**Run view HTMX branch** (per view):
- HTMX request (with `HX-Request` header) → 204, no redirect
- Non-HTMX request → redirect to detail page (existing behaviour unchanged)

### Template / view rendering tests

For each list view:
- Run button is rendered and enabled when `has_active_run` is False
- Run button is rendered disabled when `has_active_run` is True
- Log button is disabled when `has_active_run` is True

### Playwright test (optional, one app is sufficient)

1. Navigate to Exports list
2. Click ▶ Run on a config
3. Assert spinner appears in Status cell immediately (before poll)
4. Assert Run and Log buttons are disabled
5. Assert Edit button is still active
