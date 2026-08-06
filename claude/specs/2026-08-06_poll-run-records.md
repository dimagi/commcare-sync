# Poll Run Records

The run button polls Django-Q2's task table, which is the wrong source of truth.
The app already records run state itself, in a row that exists before the task
is enqueued and outlives its result. Poll that instead.

This is the second of two stacked branches. It builds on
[2026-08-06_align-run-dispatch.md](2026-08-06_align-run-dispatch.md), which
makes run creation uniform across the three apps.

## Why the current design misreports

`task_status` (`apps/web/views.py`) answers from `django_q.tasks.fetch()`.
Django-Q2 only writes a `Task` row once a task _finishes_, so "not found" and
"still running" are indistinguishable, and the endpoint reports both as pending.
Three consequences:

- **A failed forwarding or refresh run shows "Complete!"** Both runners catch
  their exceptions, set `status = FAILED` and return normally, so `task.success`
  is `True`. Their tasks return a bare `run.id`; `task_status` only exposes
  `result` when it is a `dict`, so the int is dropped and the JS falls back to
  `data.success`. Exports escape this only because they happen to return a dict
  containing `status`, which the JS special-cases.
- **The poll never terminates.** No attempt cap, and every way a task can fail
  to produce a row looks like a healthy in-progress run: cluster not running,
  worker killed (redelivery is 8h out), result trimmed by `save_limit` (default
  250), or the `task_id=None` case below.
- **"Already running" hangs the button.** `_run_export` returns
  `run_response(request, task_id=None)` when a run is in flight;
  `HttpResponse(None)` has a body of `b'None'`, the JS polls
  `/tasks/None/status/`, and the button stays disabled until reload.

A single fetch error is meanwhile treated as terminal failure —
`.catch(() => finish(false))` sits on the whole chain — so the failure handling
is simultaneously too lenient and too eager.

## Goals

- The run button reflects the run's real status, identically in all three apps.
- Polling terminates, and says something honest when it gives up.
- "Already running" is a distinguishable outcome, not a sentinel body.
- Remove `task_status` and the task-id round trip entirely.

## Non-goals

- Live progress within a run. `RunBaseModel` has no progress field and the
  runners do not report one; the bar stays indeterminate. Adding real progress
  is separate work.
- Streaming or websockets. Polling at the current cadence is adequate for a
  handful of users.
- Changing what the runners do, or how runs are dispatched.

## Design

### The trigger response

`run_response` currently returns either 204 + `HX-Trigger` (HTMX callers) or a
bare task id. Replace the second branch with JSON naming the run:

```json
{ "run_id": 41, "poll_url": "/exports/runs/41/status/" }
```

and return **409** with no body when nothing was started because a run is
already active. The JS already has a path for a non-OK response; this makes it
reachable and correct.

`run_all_exports` needs no run id — its button is `hx-post`
(`exports_home.html:44`), so it always takes the 204 branch and the task id it
returns today is never read. Drop it.

### The status endpoint

One per app, alongside the existing `runs/<int:run_id>/log/`:

```python
@login_required
@require_GET
def run_status(request, run_id):
    run = get_object_or_404(ExportRun, id=run_id)
    return JsonResponse({
        'status': run.status,
        'complete': run.status in TERMINAL_STATUSES,
        'success': run.status == run.Status.COMPLETED,
    })
```

`TERMINAL_STATUSES` is `{COMPLETED, FAILED, SKIPPED, TIMEOUT}` plus exports-only
`MULTIPLE`; it belongs on `RunBaseModel` so each app does not restate it.
`TIMEOUT` arrives with the reaper in the preceding branch: a run whose worker
was killed is terminal, and omitting it here would put the poller back to
running out its attempt cap on a run that is definitively over.

`@login_required` with no per-object check matches the existing `run_log` views
and the app's single-organization model. This is not a new authorization posture
— it is the established one, which the bare task-id endpoint was not.

### The poller

```javascript
const MAX_ATTEMPTS = 150; // ~5 minutes at 2s
```

- `QUEUED` → "Queued…", `STARTED` → "Running…". The UI can finally tell these
  apart; today everything reads "Running…".
- Terminal → `finish(status === 'completed')`.
- 404 → stop, report failure. The row genuinely does not exist, which is
  unambiguous now.
- Attempts exhausted → stop and say "Still running — refresh to check". Not
  "Failed!", which would be a lie.
- Retry a fetch error once or twice before concluding anything, so a transient
  blip no longer paints a healthy run red.

Attempt exhaustion is not failure. A long export legitimately outlives any cap
we pick; the run table remains the authority and the message should point there.

### Removals

- `apps/web/views.py`: `task_status`, and the `task_id` parameter of
  `run_response`.
- `apps/web/urls.py`: the `web:task_status` route.
- `apps/web/tests/test_task_status.py`.
- `refresh_details.html:61` passes `progress_message='Running Refresh...'`,
  which `run_button_script.html` never reads — dead, and untranslated. Drop it
  or wire it up.

## Implementation order

Each step is one commit and leaves the suite green.

1. Add `TERMINAL_STATUSES` to `RunBaseModel`.
2. Add `run_status` views and routes to the three apps, with tests. Nothing
   consumes them yet.
3. Switch `run_response` to JSON + 409; update the three trigger views.
4. Rewrite the poller in `run_button_script.html` against the new endpoint,
   including the attempt cap and queued/started distinction.
5. Delete `task_status`, its route, its tests, and the `task_id` parameter.
6. Drop the dead `progress_message` parameter.

Steps 1–2 are additive, so the branch is bisectable and the switch-over is a
single reviewable commit.

## Testing

- `run_status` per app: each status maps to the right `complete`/`success` pair;
  unknown id is 404; anonymous request redirects to login.
- `MULTIPLE` counts as complete and not successful.
- Trigger views: 409 when a run is active, JSON with a working `poll_url`
  otherwise.
- Playwright, extending `test_run_button_playwright.py`, which already mocks
  `**/tasks/**` and will need repointing:
  - a run that ends `FAILED` shows "Failed!" — this is the regression that
    matters, since forwarding and refreshes get it wrong today;
  - a queued run shows "Queued…" before "Running…";
  - the cap is reached and the button re-enables with the honest message;
  - clicking while a run is active re-enables the button instead of hanging.

## Risks

- The Playwright tests intercept `**/tasks/**`; the URL shape changes, so they
  will pass vacuously if repointed carelessly. Assert the mock was hit.
- Polling a run row is a DB read every 2s per open tab, against SQLite. Cheap
  (indexed pk lookup), but the attempt cap now matters for load as well as
  correctness.
- Users of forwarding and refreshes will start seeing "Failed!" where they
  previously saw "Complete!". That is the fix working, but it will look like a
  new problem and is worth a line in the release notes.

## Open questions

- Is 5 minutes the right cap? An export legitimately runs for hours. An
  alternative is no cap while the tab is focused, backing off to 10s after the
  first minute, and stopping on blur.
- Should the button poll at all after a page reload mid-run? Today the state is
  lost. The run table shows it, so possibly not worth solving.
- Does anything else want `run_status`? The run-history table currently
  refreshes wholesale via HTMX; a per-row poll could replace that, but it is not
  needed for this change.
