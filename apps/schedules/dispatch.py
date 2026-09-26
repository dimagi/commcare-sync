"""Creating and dispatching runs.

Every run, manual or scheduled, in any app, is created here and handed
to a worker task that receives the run's ID.
"""

from django.db import transaction
from django_q.tasks import async_task


def create_run(config, *, triggered_from_ui=False, triggered_by=None):
    """Create a run for ``config``, unless one is already active.

    Returns the run, or ``None`` if the config already has an active run.

    The check and the insert share a transaction, so that two concurrent
    triggers can't both see no active run and both create one. The
    database is configured with ``transaction_mode: IMMEDIATE`` (see
    ``DATABASES`` in settings.py), which makes SQLite take its write lock
    when the transaction begins, so triggers are serialised.
    """
    with transaction.atomic():
        if config.has_active_run:
            return None
        return config.runs.create(
            config_version=config.latest_version,
            triggered_from_ui=triggered_from_ui,
            triggered_by=triggered_by,
        )


def create_run_and_dispatch(
    config,
    *,
    triggered_from_ui,
    triggered_by=None,
    task_kwargs=None,
):
    """Create a run for ``config`` and enqueue its task to perform it.

    The task is ``config.RUN_TASK``, the same one the scheduler uses. It
    is called with the run's ID and ``task_kwargs`` (e.g.
    ``{'start_over': True}``).

    Returns the Django Q2 task ID, or ``None`` if a run is already
    active.

    The run and its queue entry are committed together, in the same
    transaction as ``create_run``'s check. Django Q2's ORM broker queues
    tasks in the default database, so if ``async_task`` fails, the run is
    rolled back instead of being left QUEUED with no task to perform it,
    blocking its config.
    """
    with transaction.atomic():
        run = create_run(
            config,
            triggered_from_ui=triggered_from_ui,
            triggered_by=triggered_by,
        )
        if run is None:
            return None
        return async_task(config.RUN_TASK, run.id, **(task_kwargs or {}))
