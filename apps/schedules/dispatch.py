"""Handles creating, dispatching and claiming runs.
"""

import logging

from django.db import transaction
from django.utils import timezone
from django_q.tasks import async_task

from apps.commcare.models import RunBaseModel

logger = logging.getLogger(__name__)


def create_run(
    config,
    *,
    triggered_from_ui=False,
    triggered_by=None,
    retry_of=None,
    started=False,
):
    """Create a run for ``config``, unless one is already active.

    Returns the run, or ``None`` if the config already has an active run.
    A ``started`` run is created STARTED, for a caller that performs it
    at once instead of dispatching it.

    The check and the insert share a transaction, so that two concurrent
    triggers can't both see no active run and both create one. The
    database is configured with ``transaction_mode: IMMEDIATE`` (see
    ``DATABASES`` in settings.py), which makes SQLite take its write lock
    when the transaction begins, so triggers are serialised.
    """
    with transaction.atomic():
        if config.has_active_run:
            return None
        extra = {}
        if started:
            extra = {
                'status': RunBaseModel.Status.STARTED,
                'started_at': timezone.now(),
            }
        return config.runs.create(
            config_version=config.latest_version,
            triggered_from_ui=triggered_from_ui,
            triggered_by=triggered_by,
            retry_of=retry_of,
            **extra,
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

    Returns the run, or ``None`` if a run is already active.

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
        if run is not None:
            async_task(config.RUN_TASK, run.id, **(task_kwargs or {}))
        return run


def claim_run(run_model, run_id):
    """Return the run that a worker task should execute, marked STARTED.

    Returns ``None`` if there is nothing to do.

    If a task is stopped by a timeout, it records a failed result and is
    never delivered again. But a task whose worker died (OOM, SIGKILL,
    a reboot) does not record a result. Django Q2 delivers it again
    after ``Q_CLUSTER['retry']`` seconds, indefinitely. So use the run's
    status to determine what should happen when a task is delivered:

    * If a run's status is QUEUED, it is on its first delivery: Mark it
      STARTED and execute it
    * A run that ``reap_stale_runs`` marked TIMEOUT is retried once, as
      a new run, created STARTED, and linked to the first attempt by
      ``retry_of``. Only a run whose worker died gets here.
    * Otherwise it is under way, finished, or already retried.

    A re-delivery can arrive before its run has been reaped. It then
    finds the run STARTED, and the retry is dropped.
    """
    try:
        run = run_model.objects.select_related('config').get(id=run_id)
    except run_model.DoesNotExist:
        logger.warning(
            '%s %s no longer exists, skipping.', run_model.__name__, run_id
        )
        return None

    if run.status == RunBaseModel.Status.QUEUED:
        return _start(run)
    if run.status == RunBaseModel.Status.TIMEOUT and _can_retry(run):
        return _retry(run)
    return None


def _start(run):
    """Mark ``run`` STARTED if it is still QUEUED. Return it, or ``None``."""
    now = timezone.now()
    started = type(run).objects.filter(
        pk=run.pk, status=RunBaseModel.Status.QUEUED
    ).update(status=RunBaseModel.Status.STARTED, started_at=now)
    if not started:
        return None
    run.status = RunBaseModel.Status.STARTED
    run.started_at = now
    return run


def _retry(run):
    """Create and return a STARTED retry of ``run``, or ``None``."""
    run_model = type(run)
    retry = create_run(
        run.config,
        triggered_from_ui=run.triggered_from_ui,
        triggered_by=run.triggered_by,
        retry_of=run,
        started=True,
    )
    if retry is None:
        logger.info(
            '%s %s timed out, but its config already has an active run. '
            'Not retrying.',
            run_model.__name__, run.id,
        )
    else:
        logger.warning(
            '%s %s timed out. Retrying it as %s %s.',
            run_model.__name__, run.id, run_model.__name__, retry.id,
        )
    return retry


def _can_retry(run):
    """Returns ``True`` if ``run`` is an original run that has not been
    retried.
    """
    if run.retry_of_id is not None:
        return False
    return not type(run).objects.filter(retry_of=run).exists()
