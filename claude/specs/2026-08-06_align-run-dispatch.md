# Align Run Dispatch

Exports, forwarding and refreshes each create a run record and enqueue work in
their own way. The differences are not deliberate — they are what four
separately-written dispatch paths drifted into. Collapse them onto one pair of
helpers in `apps/schedules/`, so that a run is created, guarded and dispatched
the same way whichever app and whichever trigger it came from.

This is the first of two stacked branches. The second
([2026-08-06_poll-run-records.md](2026-08-06_poll-run-records.md)) reworks how
the UI observes a run once it exists, and depends on the run records this branch
makes uniform.

## Current state

|                              | Exports (single & multi)       | Forwarding            | Refreshes                             |
| ---------------------------- | ------------------------------ | --------------------- | ------------------------------------- |
| Manual: run row created      | in the view                    | in the view           | in the view                           |
| Manual: concurrency guard    | `has_active_run`               | **none**              | **none**                              |
| Scheduled: queue hops        | **2**                          | 1                     | 1                                     |
| Scheduled: concurrency guard | `has_queued_runs()`            | **none**              | inline `status__in=[QUEUED, STARTED]` |
| Re-delivery guard in worker  | single only                    | none                  | none                                  |
| Missing run row              | unguarded `.get()`, task fails | caught, task succeeds | caught, task succeeds                 |
| Timeout                      | global 6h                      | global 6h             | 3660s                                 |

Four guard behaviours for one concept, and `ScheduleMixin.has_active_run`
already expresses the correct one (any run `QUEUED` or `STARTED`) while
refreshes hand-rolls that exact query and exports uses a weaker one.

There is also a fifth dispatch path nobody maintains: the `run_all_exports`
management command, which creates runs inline with no guard and no attribution.

## Goals

- One concurrency guard, one meaning, applied on every trigger path.
- One place that creates the run row, and one that creates it and enqueues the
  work.
- Every worker safe against Django-Q2 re-delivery.
- Uniform handling of a run row that has gone missing.
- No run stuck `STARTED` forever after its worker is killed.

## Non-goals

- **Generalising "Run All".** It stays exports-only. Fetching all data at once
  is a thing users want; refreshing every materialized view or forwarding to
  every third-party API at once is not. This is a product decision, not drift,
  and the spec should not erase it.
- Changing the run-button UI or how it observes progress — that is the follow-up
  branch. In particular, the "already running" outcome keeps returning
  `run_response(request, task_id=None)` here; the follow-up replaces that
  sentinel with a 409 in all three apps at once.
- Changing schedule semantics: `next_run_at`, the claim step in
  `run_due_schedules`, and periodicity computation are all untouched.
- `start_over` remains exports-only; it has no meaning for the other two.

## Design

### Two helpers, not one

The scheduled paths do the work inline — `run_scheduled_forwarding_task` calls
`run_forwarding(fwd_run)` directly, refreshes likewise, and the exports hop
collapse below makes exports match. Only the manual paths enqueue a second task.
So the shared part is guard-plus-create, and dispatch sits on top of it:

```python
# apps/schedules/dispatch.py

def create_run(config, *, triggered_from_ui=False, triggered_by=None):
    """Create a run for ``config``, unless one is already active.

    Returns the run, or None if the config already has an active run.

    The check is not atomic: two concurrent triggers can both observe no
    active run and both create one. The window is small and this is no
    worse than the behaviour it replaces, but it is real. Hardening it
    needs ``select_for_update`` on the config row inside a transaction,
    which is worth doing only if duplicate runs are observed in practice.
    """
    if config.has_active_run:
        return None
    return config.runs.create(
        config_version=config.latest_version,
        triggered_from_ui=triggered_from_ui,
        triggered_by=triggered_by,
    )


def create_run_and_dispatch(config, task, *, triggered_by=None, **task_kwargs):
    """Create a run for ``config`` and enqueue ``task`` to perform it.

    For manual triggers, which enqueue the work rather than doing it.
    Returns ``(run, task_id)``, or ``(None, None)`` if a run is active.
    ``task_kwargs`` are passed to ``task`` (e.g. ``start_over``).
    """
    run = create_run(
        config, triggered_from_ui=True, triggered_by=triggered_by
    )
    if run is None:
        return None, None
    return run, async_task(task, run.id, **task_kwargs)
```

Scheduled tasks call `create_run(config)` and then run the work inline; views
call `create_run_and_dispatch`. A single helper that always enqueued would
re-introduce the very hop the exports collapse removes.

Two details make this work without per-app configuration:

- `config.runs` is a reverse manager on all four run models, so `.create()` sets
  the config FK itself and the differing names never appear.
- The version FKs are byte-identical apart from their names.

### Rename the run FKs

`base_export_config` / `forwarding_config` / `refresh_config` and
`export_config_version` / `forwarding_config_version` / `refresh_config_version`
all become `config` and `config_version`.

Rename rather than hoist into `RunBaseModel`. `MultiProjectPartialExportRun`
inherits `RunBaseModel` via `ExportRunBase` but belongs to a parent run, not a
config — hoisting would give it a permanently-null `config_version` column.

`config_version` is what the helper names directly. `config` is not required by
the helper (the reverse manager sets it), but renaming both together is one
mechanical pass rather than two, and `run.config` reads better than three names
for one relationship.

### One timeout

`RefreshConfig.SCHEDULED_TASK_OPTIONS = {'timeout': 3660}` is not a workload
constraint. It is residue from Celery: the original decorator was
`@shared_task(soft_time_limit=3600, time_limit=3660)`, the conventional pair of
a one-hour soft limit that raises inside the task plus a hard backstop a minute
later. `SoftTimeLimitExceeded` was never caught, and Django-Q2 has a single
`timeout` with no soft/hard split, so the port kept the backstop and dropped the
number that carried the intent.

An hour is in any case too short. Some materialized views build large JSON
payloads sent monthly; they legitimately take hours, and nothing reads them
until a forwarder picks them up a day later. Killing one at an hour would be the
bug, not the timeout working.

So: delete `SCHEDULED_TASK_OPTIONS` entirely and let everything use the 6h
`Q_CLUSTER` global. That removes the attribute, the `dict()` copying at every
call site, the tests asserting the copy is not shared, the `ScheduleMixin`
docstring paragraph explaining who must forward it, the `q_options` argument in
`run_due_schedules`, the workaround in `_create_and_dispatch_export_run`, and
the duplicated `3660` literal in `refreshes/views.py`.

If a per-config timeout is ever wanted again it will be to make refreshes
_longer_ than the global, not shorter, and re-adding it is cheap.

Note that `Q_CLUSTER['retry']` (8h) must stay greater than `timeout` (6h). If
the global timeout is ever raised, `retry` has to move with it.

### Collapse the exports queue hop

`run_scheduled_export_task` currently creates a run and enqueues
`run_export_task` — a second hop that exists only because celery-beat used to
call it. Forwarding and refreshes do the work inline in their scheduled task.
Make exports match: the scheduled task creates the run and calls
`run_export(run)` directly.

This makes the manual/scheduled split identical in all three apps: manual
enqueues a work task from the view, scheduled performs the work inline.

### The guard queries the database

`has_active_run` short-circuits on a `_all_runs` prefetch. That prefetch has
exactly one consumer — `config_table.html:66`, fed by the three list views — and
a list snapshot is the wrong thing for a correctness guard to consult.

Invert it: `has_active_run` always queries, and the template opts into a
`has_active_run_cached` property that reads the prefetch. Correct by default,
fast where the fast path is actually set up.

`has_queued_runs()` — which only inspects whether the _most recent_ run is
`QUEUED` — has no callers once exports adopt the helper. Delete it and its tests
in three apps.

### Guard placement

Keep the guard where the run is created — in the view for manual runs, in the
scheduled task for scheduled ones — rather than in `run_due_schedules`. The
dispatcher has already claimed the slot by advancing `next_run_at`; a config
that is skipped because it is still running should lose that slot, which is what
the current shape does.

### Re-delivery guard

`run_export_task` bails out with `if export_run.status != QUEUED: return`.
Nothing else does, so with `max_attempts: 2` and `retry: 8h` a re-delivered
multi-export, forwarding or refresh task redoes the work. Add the same guard to
all four workers.

`ack_failures: True` means a task that raises is not re-delivered, so this only
covers timeouts and worker deaths — which is exactly the case where the work may
still have had effects.

### Reap stale runs

A run whose worker was killed stays `STARTED` forever, which under the guard
above blocks its config permanently. All four runners set `started_at` at the
moment they set `STARTED`, so a `STARTED` run older than the task timeout cannot
still be running.

`run_due_schedules` already runs every minute and already iterates all four
config models. Before the due-config loop, mark expired `STARTED` runs
`TIMEOUT`, set `completed_at`, and note the reason in `log`. One bulk `UPDATE`
per run model per minute.

Reaping rather than merely filtering them out of the guard matters: the row is
also what the run-history table renders and what the follow-up branch's status
endpoint reports. Filtering would unblock the config while leaving the UI
claiming a run that ended hours ago is still going.

`MultiProjectPartialExportRun` rows are reaped alongside their parent, for the
same run-history honesty, even though they gate nothing.

Stale `QUEUED` runs are deliberately **not** reaped. A run enqueued while the
cluster is down has no `started_at` to measure from, and `created_at` is not a
safe substitute — with two workers a run can legitimately sit queued a long time
behind other work, and no absolute cap can tell that apart from a lost one.
Killing a run that was going to be fine is worse than leaving a stuck one
visible.

### A `TIMEOUT` status

A reaped run is not a run that failed. The work may have been fine and the
cluster restarted under it; an administrator looking at run history needs to
tell "this export is broken" from "this export was cut off". So add
`TIMEOUT = 'timeout', _('Timed out')` rather than reusing `FAILED`.

The status field is `max_length=10`, so `'timeout'` fits without a column
change, but the choices live in two enums and the value has more consumers than
it first appears:

- `RunBaseModel.Status` **and** `ExportRunBase.Status`, which re-declares the
  whole enum in order to add `MULTIPLE`. That duplication is pre-existing and
  this change makes it bite twice; worth a look, but not worth fixing here.
- `RunBaseModel.has_log` — a timed-out run has partial output worth reading, so
  `TIMEOUT` joins `COMPLETED` and `FAILED`.
- `to_status_icon` in `exports/templatetags/exports_tags.py`, which maps status
  to icon and colour for every app via `config_table.html`. It looks up with
  `.get()` and no fallback, so an unmapped status renders
  `class="fa-solid None None"` — a silent visual break, not an error. Needs an
  entry: `fa-clock` and `text-warning` alongside `MULTIPLE`.
- The status filter checkboxes in `web/components/run_history.html`. They are
  hardcoded and every one ships `checked`, so a sixth is needed or timed-out
  runs vanish from the default view. `_VALID_RUN_STATUSES` in
  `commcare_sync/views.py` derives from `RunBaseModel.Status.values` and needs
  no change.
- `apps/web/stats.py` counts failures per app by `status=FAILED`. Whether
  timeouts should count toward the dashboard's failure figures is a judgement
  call; they should, since both mean "this run produced nothing".
- The follow-up branch's `TERMINAL_STATUSES` must include it. Noted in that
  spec.

`has_active_run`, `last_run`, `mark_skipped` and the re-delivery guard all
derive from `QUEUED`/`STARTED` and need no change.

Adding a choice is an `AlterField` migration on each of the five concrete run
models, with no data change.

### Missing run rows

Exports let `DoesNotExist` propagate (task recorded as failed); forwarding and
refreshes catch it and return `None` (task recorded as successful). Pick
catching-and-logging for all four: a deleted run is an expected race, not a task
failure. Log at `warning`, not `error`, matching the exports scheduled tasks.

### Loose ends

- `run_export_task(export_run_id, start_over)` takes `start_over` as a required
  positional, the only asymmetry among the four workers. Give it a default of
  `False`; starting over is the rare case.
- The `run_all_exports` management command creates runs inline, bypassing every
  guard. Replace its body with a call to `run_all_exports_task()`, so it shares
  the "Run All" button's path.
- Drop the redundant `status=Status.QUEUED` passed on create — it is the field
  default.

## Implementation order

Each step is one commit and leaves the suite green.

1. Rename the FKs to `config` and `config_version` on the four run models.
   Migrations plus a mechanical call-site sweep, including the `run_all_exports`
   management command. No behaviour change.
2. Delete `SCHEDULED_TASK_OPTIONS` and everything that carried it. **Behaviour
   change**: refreshes go from a 3660s timeout to the 6h global.
3. Add the `TIMEOUT` status: both enums, `has_log`, `to_status_icon`, the filter
   checkbox, the dashboard failure counts, and an `AlterField` migration per run
   model. Nothing sets it yet.
4. Reap stale `STARTED` runs in `run_due_schedules`.
5. Make `has_active_run` always query; add `has_active_run_cached` and point the
   template at it.
6. Add `apps/schedules/dispatch.py` with both helpers, plus tests against one
   app.
7. Adopt them in exports; collapse the scheduled hop; default `start_over` to
   `False`; point the management command at `run_all_exports_task`. **Behaviour
   change**: the scheduled guard tightens from `has_queued_runs()` to
   `has_active_run`, so a scheduled export is now skipped while an earlier run
   is still `STARTED`, not only while it is `QUEUED`.
8. Adopt them in forwarding. **Behaviour change**: forwarding gains a
   concurrency guard on both paths.
9. Adopt them in refreshes; delete the hand-rolled `status__in` filter.
   **Behaviour change**: the manual button gains a guard.
10. Add the re-delivery guard to all four workers.
11. Cleanups: delete `has_queued_runs` and its tests; uniform missing-row
    handling and log levels; drop the redundant `status=Status.QUEUED`.

Steps 3 and 4 land before the guards so that no step in the branch can leave a
config blocked by a run that has already died. Splitting the status from the
reaper keeps the wide-but-shallow enum sweep separate from the logic that uses
it.

## Testing

- `create_run`: creates the run, sets attribution, returns `None` and creates
  nothing when a run is active.
- `create_run_and_dispatch`: enqueues the task with the run id and any extra
  kwargs; enqueues nothing and returns `(None, None)` when a run is active.
- Guard coverage per app per path — manual and scheduled, `QUEUED` and `STARTED`
  — including the three paths whose behaviour changes.
- `has_active_run` ignores a stale `_all_runs` prefetch; `has_active_run_cached`
  uses it.
- Re-delivery: calling a worker twice performs the work once.
- Missing run row: task logs and returns without raising, for all four.
- The exports hop collapse: a scheduled export performs the work without a
  second `async_task` call.
- Reaper: a `STARTED` run older than the timeout becomes `TIMEOUT` and stops
  blocking its config; one inside the timeout is untouched; a `QUEUED` run of
  any age is untouched; partial runs are reaped with their parent.
- `TIMEOUT` renders an icon rather than `class="fa-solid None None"`, is
  selected by default in the status filter, has a log, and counts toward the
  dashboard failure figures.

## Risks

- **Forwarding and refreshes gain guards they never had.** If anyone depends on
  overlapping forwarding runs — several forwards to different destinations from
  one config — this silently stops them. Worth confirming before step 7. The
  guard is per config, so distinct configs are unaffected.
- **The FK rename touches three apps' migrations.** Mechanical, but it is the
  step most likely to conflict with other in-flight work, which is why it goes
  first and alone.
- Collapsing the exports hop changes what a Django-Q2 task boundary wraps, so an
  export that used to be retried as two small tasks is now retried as one long
  one. This is the same shape forwarding and refreshes already have.
- The reaper writes to run rows on a schedule. A bug there corrupts run history
  rather than merely failing to dispatch, so its query bounds deserve more
  scrutiny than their size suggests.

## Open questions

- `ExportRunBase` re-declares the whole `Status` enum to add one member, so
  every status change has to be made twice. Adding `TIMEOUT` makes that concrete
  without fixing it. Is it worth a separate pass to give `RunBaseModel` the one
  enum and exports a way to extend it?
