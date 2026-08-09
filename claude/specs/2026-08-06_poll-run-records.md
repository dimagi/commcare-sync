# Poll Run Records

The run button polls Django Q2's task table, which is the wrong source of truth.
The app already records run state itself, in a row that exists before the task
is enqueued and outlives its result. Poll that instead.

## Why the current design misreports

`task_status` (`apps/web/views.py`) answers from `django_q.tasks.fetch()`.
Django Q2 only writes a `Task` row once a task _finishes_, so "not found" and
"still running" are indistinguishable, and the endpoint reports both as pending.
Three consequences:

- **A failed forwarding or refresh run shows "Complete"** Both runners catch
  their exceptions, set `status = FAILED` and return normally, so `task.success`
  is `True`. Their tasks return a bare `run.id`; `task_status` only exposes
  `result` when it is a `dict`, so the int is dropped and the JS falls back to
  `data.success`. Exports escape this only because they happen to return a dict
  containing `status`, which the JS special-cases — and only on the happy path:
  the re-delivery guards return a bare `None` (`exports/tasks.py:120`,
  `forwarding/tasks.py:35`, `refreshes/tasks.py:30`), which reads as "Complete"
  too.

- **The poll never terminates.** No attempt cap, and every way a task can fail
  to produce a row looks like a healthy in-progress run: cluster not running,
  worker killed (redelivery is 24h out, `settings.py:218`), result trimmed by
  `save_limit` (default 250), or the `task_id=None` case below.

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
bare task ID. Replace the second branch with JSON naming the run:

```json
{ "run_id": 41, "poll_url": "/exports/runs/41/status/" }
```

and return **409** when nothing was started because a run is already active,
with a body naming the reason so the button has something honest to say:

```json
{ "error": "already_running" }
```

The key is part of the contract the new trigger-view tests assert, so it is
named here rather than left to the implementation.

Note that the JS does _not_ currently have a working path for a non-OK response,
contrary to how the `.catch` at `run_button_script.html:75` reads: `fetch()`
does not reject on an error status, so today a 409 would flow into the success
path with an empty body and the poller would chase `undefined`. The rewritten
poller must branch on `response.ok` explicitly.

409 is not the only non-OK answer the trigger can give, and the other two are
not hypothetical: an expired session redirects the POST to the login page, which
arrives as `response.ok` with an HTML body, and a rotated CSRF token gives 403.
The trigger therefore takes the same two rules the poller does below — a
response that is OK but not JSON means "Session expired — refresh", any other
non-OK response re-enables the button with a generic failure — rather than
leaving them to the `.catch` that only reaches the console today.

Two callers, two axes. `run_response(request, run)` decides on `HX-Request`
first: HTMX callers keep their 204 + `HX-Trigger` whether or not a run was
started, because the table refresh is the right answer either way and the
refreshed table shows the active run. Only the JSON branch distinguishes 200
from 409.

`poll_url` comes off the run itself: add a `status_url` property to each run
model, mirroring the `run_url`, `edit_url` and `last_run_log_url` properties the
configs already carry (`exports/models.py:62,112`, `forwarding/models.py:113`,
`refreshes/models.py:54`). Without it, `run_response` cannot reverse the route —
`_run_export` (`exports/views.py:403`) is shared by `ExportConfig` and
`MultiProjectExportConfig`, so the URL name is not knowable from the function —
and the alternative is threading a URL name through every trigger view. One
property per run model keeps each route named next to the model it belongs to.

`run_all_exports` has no run to name: it calls `async_task` directly rather than
`create_run_and_dispatch`, and its button is `hx-post` (`exports_home.html:44`),
so it always takes the 204 branch and the task ID it returns today is never
read. Because `run_response` decides on `HX-Request` first, passing `run=None`
would in fact be safe — the branch where `None` means "already active" is never
reached. Have it return the 204 + `HX-Trigger` itself anyway, so that safety
does not rest on a caller always sending the header: a `curl`, or a second
non-HTMX caller added later, would otherwise get "already running" for a run
that was just started.

### The status endpoint

One per run model that a button watches, alongside the existing
`runs/<int:run_id>/log/`. That is **four**, not three: exports polls both
`ExportRun` and `MultiProjectExportRun` (`export_details.html:71`,
`multi_project_export_details.html:10`), mirroring the existing
`run_log`/`multi_run_log` split at `exports/urls.py:83-87`. Returning `poll_url`
from the trigger view rather than building it in the browser is what keeps the
shared button template ignorant of which model it is watching.

Four, though there are **five** run models: `MultiProjectPartialExportRun`
(`exports/models.py:177`) is an `ExportRunBase` too, and is in `RUN_MODELS` for
reaping (`schedules/tasks.py:46-52`). It hangs off a parent run rather than a
config, has no button and no `has_active_run`, so nothing polls it and it gets
no endpoint.

Four endpoints also means four route _names_, so exports carries two:
`run_status` at `runs/<int:run_id>/status/` and `multi_run_status` at
`runs/multi-project/<int:run_id>/status/`, again mirroring the log pair.
`MultiProjectExportRun.status_url` reverses the second, and nothing else can:
one name serving both would silently point half the polls at the wrong table.

The payload lives in one place, so the contract cannot drift across four copies:

```python
# apps/web/views.py
def run_status_response(model, run_id):
    run = get_object_or_404(model, id=run_id)
    response = JsonResponse({
        'status': run.status,
        'label': run.get_status_display(),
        'complete': run.is_terminal,
    })
    response['Cache-Control'] = 'no-store'
    return response
```

```python
# apps/exports/views.py
@login_required
@require_GET
def run_status(request, run_id):
    return run_status_response(ExportRun, run_id)


@login_required
@require_GET
def multi_run_status(request, run_id):
    return run_status_response(MultiProjectExportRun, run_id)
```

An earlier draft also sent a `success` boolean derived as `status == COMPLETED`,
which would relabel two non-failures as "Failed": `TIMEOUT`, set by
`reap_stale_runs`, and `SKIPPED`, set by the `clear_queued_runs` command. The
poller keys off `status` directly and can render each one properly.

`label` is `get_status_display()` — the status's own translated label, from the
same `TextChoices` the poller would otherwise have to restate. Sending it means
the browser never enumerates statuses for _wording_, only for colour, so a
status added later reads correctly the moment it is defined instead of rendering
`undefined` until someone remembers the JS. `status` is still sent because
colour is a presentation choice the server has no business making, and because
keying a class off a translated string would break under translation.

One label needs correcting first. `MULTIPLE`'s is "Multiple statuses"
(`exports/models.py:136`), which implies the partial runs disagreed — but
`runner.py:36-40` sets `MULTIPLE` whenever the set of partial-run statuses is
not exactly one, and the usual case is a multi-project export whose projects all
succeeded. Change it to `_('Multiple results')`, which is true in both cases.
This is a `choices` change, so it needs a migration altering `status` on all
three `ExportRunBase` tables.

The blast radius is smaller than it looks. No template calls
`get_status_display`: the run-history badge renders from the raw value via
`to_status_icon`, and the status-filter checkboxes carry their own hardcoded
`{% trans %}` labels (and have no `MULTIPLE` entry at all). So today the label
is visible only in the Django admin — and, after this change, in `label`. That
makes the correction cheap now and worth doing now, because `label` is about to
put this string in front of every user for the first time.

(An empty set also lands in `MULTIPLE`: a multi-project config with no projects
produces no partial runs, so `len(run_statuses) == 1` is false. Terminal either
way, so the poller is unaffected, and "Multiple results" is no less accurate
there than the wording it replaces.)

`is_terminal` is a property on `RunBaseModel`, defined as the complement of
`ACTIVE_RUN_STATUSES` (`schedules/mixin.py:27`) rather than as its own
enumeration of terminal states. Enumerating would not work as written:
`ExportRunBase` (`exports/models.py:128`) redefines `Status` wholesale to add
`MULTIPLE`, so a `TERMINAL_STATUSES` constant on the base class would have to be
restated in the subclass — the restatement the constant exists to avoid. The
complement gets `MULTIPLE` for free, shares one source of truth with
`has_active_run`, and makes any status added later terminal by default instead
of poll-forever by default. `ACTIVE_RUN_STATUSES` moves to
`apps/commcare/models.py` beside `RunBaseModel`, since the import already runs
in that direction; `has_active_run` imports it back into `schedules/mixin.py`,
which is its only other user, so no re-export shim is needed.

The complement holds across `ExportRunBase`'s redefined `Status` for a reason
worth stating: `TextChoices` members are `str` subclasses whose values are
unchanged in the subclass, so `self.status not in ACTIVE_RUN_STATUSES` compares
equal strings whichever `Status` the row's class declares. A subclass that
renamed the value of `QUEUED` or `STARTED` would break it — none does, and one
that tried would break `has_active_run` first.

`TIMEOUT` cannot in fact arrive mid-poll: `reap_stale_runs` measures from
`Q_CLUSTER['timeout']`, which is now 23 hours (`settings.py:208`) plus
`REAP_MARGIN`, so no ceiling we would pick reaches it. It is terminal because
the complement makes it so, and because a page opened on an already-reaped run
must not poll a run that is definitively over. The same holds for `SKIPPED`,
which arrives out of band from `clear_queued_runs`. Neither needs the poller to
_observe_ the transition; both need it to recognise the state.

`is_terminal` lands directly below `has_log` (`commcare/models.py:59-65`), which
is a hand-written enumeration of `{COMPLETED, FAILED, TIMEOUT}` — a third
near-terminal set, excluding `SKIPPED` and `MULTIPLE`. Leave it alone: it asks a
different question (did this run produce a log?) and answers it correctly. But
it is the first thing a reader will see next to the argument above, so it is
worth saying that the collision was noticed rather than missed.

`@login_required` with no per-object check matches the existing `run_log` views
and the app's single-organization model. This is not a new authorization posture
— it is the established one, which the bare task-id endpoint was not.

### The poller

- Every message about the run itself is `label`, verbatim. `QUEUED` reads
  "Queued" and `STARTED` reads "Started", which the UI can finally tell apart;
  today both read "Running...". Only the messages that are about the _poller_
  rather than the run — already running, session expired, gave up — are written
  in the JS, because no status describes them.
- The first poll fires as soon as the trigger responds, not one interval later,
  so a run that finishes in under a second is never sat behind "Waiting for task
  to start...". The interval governs subsequent polls only.
- Terminal → `label` and a colour keyed off `status`, following the badge
  mapping that already exists in `exports/templatetags/exports_tags.py:21-37`:
  success for `COMPLETED`, danger for `FAILED`, warning for `TIMEOUT` and
  `MULTIPLE`, muted for `SKIPPED`.
- A terminal status the colour map doesn't know → a neutral colour, still
  labelled by the server. `is_terminal` is deliberately terminal-by-default so a
  status added later cannot poll forever; the colour map is the one remaining
  enumeration, and a fallback keeps that addition from rendering uncoloured-
  by-accident rather than uncoloured-by-choice.
- Resetting the bar means removing every colour class it can carry, including
  the `bg-primary` baked into its markup (`run_history.html:162`). Today's
  `finish()` removes only `bg-success` and `bg-danger`, so with a third and
  fourth colour in play the rendered outcome would otherwise depend on
  stylesheet order rather than on the status. Removing `bg-primary` is safe to
  leave removed for a second run in the same page load: Bootstrap's
  `.progress-bar` is already primary-coloured via `--bs-progress-bar-bg`, so the
  class is decoration on the default rather than the source of it.
- 409 from the trigger → "Already running", re-enable the button, and fire the
  same `#run-table` refresh a terminal status does. Not an error: the run that
  blocked this click is the thing the user needs to see, and the HTMX branch
  already answers this case with a refreshed table.
- 404 from the status endpoint → stop, report failure. The row genuinely does
  not exist, which is unambiguous now.
- Retry a fetch error once or twice before concluding anything, so a transient
  blip no longer paints a healthy run red. The retry counter resets on every
  successful poll, so a long run cannot accumulate its way to a false failure.
- A response that is OK but not JSON → stop and say "Session expired — refresh".
  `@login_required` answers an expired session with a redirect to the login
  page, which arrives as `response.ok` with an HTML body, so `.json()` throws.
  Left to the retry rule above that reads as a transient blip and then as "Still
  running". A poll that may legitimately run for half an hour makes this
  reachable, so branch on `response.redirected` or the content type before
  parsing.
- Ceiling reached → stop and say "Still running — refresh to check". Not
  "Failed", which would be a lie.

Giving up is not failure. A long export legitimately outlives any ceiling we
pick; the run table remains the authority and the message should point there.

#### Re-enabling the button

Four of the branches above end the poll without the run having completed —
already running, 404, session expired, ceiling — and each says "re-enable the
button". That is not `runButton.disabled = false`. The button is
`:disabled="running"` against the `x-data="{ running: false }"` on
`run_history.html:2`, so Alpine reasserts `running` on its next tick and the
button goes straight back to disabled. Re-enabling means clearing Alpine's
`running`, exactly as `finish()` already does.

Which is a problem for the message, because the whole progress region is
`<div id="run-status-progress" x-show="running">` (`run_history.html:158`).
Clearing `running` unmounts `#progress-bar-message` along with the bar, so
"Already running", "Session expired — refresh" and "Still running — refresh to
check" are written into a node that is then hidden. Today's `finish()` only
escapes this by writing "Complete!" and clearing `running` a second later, which
is long enough to read a one-word outcome by coincidence rather than by design.

These four messages are the ones that most need reading — three of them tell the
user to do something. Move them out of the `x-show` region: render them into a
Bootstrap alert that sits beside the run button and persists until the next
click, and let the progress bar disappear with `running` as it does now.
Terminal statuses keep the existing behaviour, message in the bar and a
one-second pause before the table refresh, because there the refreshed table is
the follow-up and the message is only a hand-off to it.

#### Cadence

A fixed 2s poll for a fixed number of attempts makes the cap do two jobs badly:
it has to be short enough to bound the load of an abandoned tab and long enough
to cover a real run. Separate them.

The interval is a function of elapsed time, not of attempt number: it grows, so
the two stop tracking each other.

```javascript
const MIN_INTERVAL = 2_000;
const MAX_INTERVAL = 10_000;
const MAX_ELAPSED = 30 * 60_000; // 30 minutes

// Check about ten times per elapsed-time scale, never faster than 2s,
// never slower than 10s.
const interval = (elapsed) =>
  Math.min(MAX_INTERVAL, Math.max(MIN_INTERVAL, elapsed / 10));
```

A ramp rather than a ladder of fixed tiers. Tiers make the reviewer take two
breakpoints on faith and give a run that finishes at 31s a 5s wait where one
finishing at 29s waited 2s — a discontinuity with no explanation a user could
follow. The ramp reaches the 10s ceiling at 100s elapsed and holds it, so it
polls fast for about the same first minute the tiers did and costs about the
same across the ceiling; the difference is that it takes one line and three
numbers to say so.

The ceiling on the _interval_ is the part that matters. Uncapped growth would
save requests — load is one indexed primary-key read, so there is nothing worth
saving — and pay for them with unbounded staleness at the tail, leaving a run
that finished at minute 25 spinning for minutes afterwards. That is the reload
this change exists to remove.

All three constants must be overridable, or the ceiling cannot be tested: as
`const`s inside the `DOMContentLoaded` closure they are unreachable from
Playwright, and the test below would have to wait out the real 30 minutes.

Template parameters of `run_button_script.html` are the wrong lever. The
Playwright tests navigate to the real detail pages, which include the template
with its defaults, so a parameter is only reachable from a test-only view, URL
and template — a page whose only purpose is to be polled.

Instead read the cadence from an optional `window.RUN_BUTTON_POLL_CONFIG` at
click time, falling back to the values above when it is absent, so a test sets
it with `page.add_init_script` before navigating and production ships no
test-only route. Three scalars pass through such an object cleanly, which a
ladder of pairs would not. The defaults stay in the template as the single
declaration of the real cadence.

Polling also stops while `document.hidden` and resumes on `visibilitychange`,
with an immediate poll on resume so a tab returned to after a while is correct
at once rather than up to 10s stale. Time spent hidden does not count toward
`MAX_ELAPSED` — a backgrounded tab is not an abandoned one.

Backing off and pausing is what makes a 30-minute ceiling affordable: an open
tab watching a long export costs six reads a minute rather than thirty, and a
hidden one costs nothing.

#### Reload mid-run

Not solved, and it does not need to be. Page state is lost on reload, so the
button stops tracking a run in flight; the run-history table on the same page is
the authority and shows it. The 409 is what makes this benign — clicking again
after a reload now gets an honest "Already running" instead of hanging on
`/tasks/None/status/` as it does today.

### Removals

- `apps/web/views.py`: `task_status`, the now-unused
  `from django_q.tasks import fetch`, the `task_id` parameter of `run_response`,
  and the "Direct callers … get the Django-Q task ID" line in its docstring.
  `login_required` also becomes unused here — `task_status` is its only user in
  this module, and the new status views are decorated in their own apps — so
  ruff will flag the import if it stays. `JsonResponse` stays, now for
  `run_status_response`, which also wants `get_object_or_404` alongside the
  `render` already imported.
- `apps/web/urls.py`: the `web:task_status` route.
- `apps/web/tests/test_task_status.py`.
- `refresh_details.html:61` passes `progress_message='Running Refresh...'`,
  which `run_button_script.html` never reads — dead, and untranslated. Drop it
  rather than wire it up: the new poller takes every message about the run from
  the server's `label`, so there is nothing left for a caller-supplied string to
  say.

`create_run_and_dispatch` keeps its `(run, task_id)` signature. The trigger
views simply stop reading the second element, which is still worth having for
logging; narrowing the return would churn `schedules/tests/test_dispatch.py` for
nothing.

## Implementation order

Each step is one commit and leaves the suite green.

1. Relabel `MULTIPLE` as "Multiple results", with its migration. Independent of
   everything below, and it stands on its own as a wording fix.
2. Move `ACTIVE_RUN_STATUSES` beside `RunBaseModel` and add `is_terminal`.
3. Add the four `run_status` views, routes and `status_url` properties, with
   tests. Nothing consumes them yet.
4. Switch `run_response` to JSON + 409; give `run_all_exports` its own 204;
   update the trigger views and the tests listed under Testing below.
5. Add the persistent alert beside the run button that the poller's non-terminal
   endings write into.
6. Rewrite the poller in `run_button_script.html` against the new endpoint:
   server-supplied labels, status-keyed colours, backoff, visibility pause,
   elapsed-time ceiling, overridable cadence constants.
7. Delete `task_status`, its route, its tests, and the `task_id` parameter.
8. Drop the dead `progress_message` parameter.

Steps 1–3 and 5 are additive, so the branch is bisectable and the switch-over is
a single reviewable commit.

## Testing

- `run_status`, for each of the four run models: every status reports the right
  `complete` and its own `label`; unknown ID is 404; anonymous request redirects
  to login; the response carries `Cache-Control: no-store`.
- `status_url` on each run model reverses to that model's endpoint, so a run
  cannot hand the button a URL that polls the wrong table.
- `MULTIPLE` counts as complete and labels itself "Multiple results", and
  `TIMEOUT` and `SKIPPED` are complete without being reported as failures.
- Trigger views: 409 when a run is active, JSON with a working `poll_url`
  otherwise, and 204 for an HTMX caller in both cases.
- `run_all_exports` still answers 204, which the shared helper no longer
  guarantees it — it is now the one caller whose contract is preserved by a
  special case.
- Playwright, extending `test_run_button_playwright.py`:
  - a run that ends `FAILED` shows "Failed" — this is the regression that
    matters, since forwarding and refreshes get it wrong today;
  - a queued run shows "Queued" before "Started";
  - a status response that is OK but HTML — the login redirect — stops the poll
    and says "Session expired", rather than retrying and then reporting "Still
    running";
  - a status fetch that fails once and succeeds on the next attempt finishes
    normally, so a transient blip no longer paints a healthy run red;
  - the elapsed-time ceiling is reached and the button re-enables with the
    honest message — this needs the `MAX_ELAPSED` override from the cadence
    section;
  - clicking while a run is active re-enables the button instead of hanging.
  - Each of the four non-terminal endings leaves its message _readable_: assert
    the alert is visible after the button is enabled again, not merely that the
    text was set at some point. Asserting on `#progress-bar-message` would pass
    against a node Alpine is about to unmount, which is the bug this guards.

The session-expired and retry cases are the two new branches with no analogue in
the current poller, and both are cheap to drive from a route handler that
fulfils HTML once, or aborts once and then fulfils. The ceiling case costs the
most and proves the least; keep it, but not at their expense.

Repointing the Playwright tests is more than swapping one glob. Each trigger
mock fulfils `text/plain` with a `test-task-id-*` body (lines 260-266, 308-313,
360-365) and must return the new JSON, including a `poll_url` the status mock
matches. For the status endpoint, match `**/runs/*/status/` — `**/runs/**` would
also swallow the run-history and `runs/<id>/log/` requests.

Six Django tests assert the old contract, not one. Only the first fails loudly;
the rest either flip on the status code or pass vacuously, so all six need
visiting:

| Test                                                                     | Today                         | Becomes                       |
| ------------------------------------------------------------------------ | ----------------------------- | ----------------------------- |
| `refreshes/tests/test_views.py:198` `test_triggers_task`                 | body `== 'test-task-id'`      | JSON with `run_id`/`poll_url` |
| `refreshes/tests/test_views.py:235` guard                                | non-HTMX post, asserts 200    | 409                           |
| `forwarding/tests/test_views.py:178` guard                               | non-HTMX post, asserts 200    | 409                           |
| `exports/tests/test_list_view.py:285`                                    | `len(content) > 0`, "task ID" | JSON with `run_id`/`poll_url` |
| `refreshes/tests/test_views.py:428` `test_non_htmx_request_returns_200`  | `len(content) > 0`            | same                          |
| `forwarding/tests/test_views.py:159` `test_non_htmx_request_returns_200` | `len(content) > 0`            | same                          |

The two guard tests are the ones to watch: they post to `config.run_url` with no
`HX-Request` header, which is exactly the branch that changes, and asserting 409
there is the new behaviour rather than a repair. Exports' own guard test
(`test_list_view.py:272`) sends `HX_REQUEST` and correctly stays 204.

## Risks

- The Playwright tests intercept `**/tasks/**`; the URL shape changes, so they
  will pass vacuously if repointed carelessly. Assert the mock was hit.
- Polling a run row is a DB read per open tab, against SQLite. Cheap (indexed pk
  lookup), and the backoff plus visibility pause is what keeps a 30-minute
  ceiling cheaper than today's uncapped 2s poll, which has no ceiling at all.
- Users of forwarding and refreshes will start seeing "Failed" where they
  previously saw "Complete". That is the fix working, but it will look like a
  new problem and is worth a line in the release notes.
- Relabelling `MULTIPLE` applies to existing rows too, since the label is not
  stored. Presentation only, and today it is visible only in the admin — but it
  is worth knowing that no data changed if someone notices the wording move.

## Open questions

- Does anything else want `run_status`? The run-history table currently
  refreshes wholesale via HTMX; a per-row poll could replace that, but it is not
  needed for this change.
