"""
Startup maintenance for the launcher.

These functions run once per launch, after ``migrate`` and before the
Django-Q2 cluster starts, to repair the state a previous process left
behind when it exited mid-run (a crash, a closed desktop window, or a
worker killed by the task timeout).

Unlike the rest of ``commcare_sync.launcher``, this module touches Django
models, so it must only be imported after ``django.setup()``. That is why
``commcare_sync/launcher/__init__.py`` does not import it at module level.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_q.models import OrmQ, Schedule

from apps.exports.models import (
    ExportRun,
    MultiProjectExportRun,
    MultiProjectPartialExportRun,
)
from apps.forwarding.models import ForwardingRun
from apps.refreshes.models import RefreshRun

logger = logging.getLogger(__name__)

# The one django-q2 Schedule row the whole scheduling subsystem hangs off.
# Keep these values in step with
# apps/schedules/migrations/0001_create_dispatcher_schedule.py.
DISPATCHER_FUNC = 'apps.schedules.tasks.run_due_schedules'
DISPATCHER_NAME = 'Run due schedules'
DISPATCHER_MINUTES = 1

# Every model that records a run and uses the QUEUED/STARTED statuses that
# gate scheduling (apps/schedules/mixin.py's has_active_run and the
# run_scheduled_* guards in apps/*/tasks.py).
RUN_MODELS = (
    ExportRun,
    MultiProjectExportRun,
    MultiProjectPartialExportRun,
    ForwardingRun,
    RefreshRun,
)

ABANDONED_MESSAGE = (
    'Abandoned: marked failed at startup after exceeding the task timeout; '
    'the process likely exited mid-run.'
)


def ensure_dispatcher_schedule():
    """
    Make sure the dispatcher Schedule row exists, and return True if it had
    to be created.

    ``migrate`` creates it, but it is editable and deletable in the django-q
    admin and never self-heals: without it nothing is ever scheduled again,
    silently.
    """
    _schedule, created = Schedule.objects.get_or_create(
        func=DISPATCHER_FUNC,
        defaults={
            'name': DISPATCHER_NAME,
            'schedule_type': Schedule.MINUTES,
            'minutes': DISPATCHER_MINUTES,
        },
    )
    if created:
        logger.warning(
            'Recreated the missing dispatcher schedule (%s)', DISPATCHER_FUNC
        )
    return created


def clear_stale_queue_locks():
    """
    Release every OrmQ lock and return how many were released.

    ``ORM.dequeue()`` hands out a task by setting ``lock = now + retry``, and
    only ``acknowledge()`` deletes the row. A task abandoned by a crash is
    therefore invisible to the broker until ``retry`` (8h) elapses. No
    cluster is running yet at launch, so every lock is stale; resetting it to
    ``now`` matches what ``enqueue()`` does and makes the task deliverable on
    the cluster's first poll.
    """
    now = timezone.now()
    alias = settings.Q_CLUSTER.get('orm') or DEFAULT_DB_ALIAS
    cleared = OrmQ.objects.using(alias).filter(lock__gte=now).update(lock=now)
    if cleared:
        logger.info('Cleared %s stale task queue lock(s)', cleared)
    return cleared


def reap_stale_runs():
    """
    Mark abandoned runs FAILED and return how many were reaped.

    A worker killed by the django-q2 ``timeout`` is terminated by signal, so
    no ``except`` block gets to mark its run row. The row stays QUEUED or
    STARTED forever, and that permanently blocks its config's schedule and
    the UI's Run button. A run older than the task timeout cannot still be
    running legitimately, so it is safe to fail it here. Younger runs are
    left alone: their queue task may yet be re-delivered (see
    ``clear_stale_queue_locks``).
    """
    timeout = settings.Q_CLUSTER.get('timeout')
    if not timeout:
        logger.warning(
            'Q_CLUSTER has no timeout; cannot tell abandoned runs from '
            'running ones, so not reaping any'
        )
        return 0

    now = timezone.now()
    cutoff = now - timedelta(seconds=timeout)
    log_line = f'{now}: {ABANDONED_MESSAGE}'
    reaped = 0
    for model in RUN_MODELS:
        stale_runs = (
            model.objects.filter(
                status__in=(model.Status.QUEUED, model.Status.STARTED)
            )
            # QUEUED runs have no started_at, and a run queued long ago is
            # just as abandoned as one that started long ago.
            .annotate(began_at=Coalesce('started_at', 'created_at'))
            .filter(began_at__lt=cutoff)
        )
        for run in stale_runs:
            run.status = model.Status.FAILED
            run.log = f'{run.log}\n{log_line}' if run.log else log_line
            run.completed_at = now
            run.save(
                update_fields=['status', 'log', 'completed_at', 'updated_at']
            )
            reaped += 1
    if reaped:
        logger.warning('Marked %s abandoned run(s) as failed', reaped)
    return reaped
