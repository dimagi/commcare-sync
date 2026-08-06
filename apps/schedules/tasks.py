"""The scheduling dispatcher.

A Django Q2 Schedule runs ``run_due_schedules`` every minute. (See
``apps/schedules/migrations/0001_create_dispatcher_schedule.py``.) It
enqueues a run for every config whose ``next_run_at`` has passed and
advances the config's ``next_run_at``. This way overdue schedules catch
up with exactly one run the next time the cluster is running.

Advancing ``next_run_at`` is a *claim*: it is a conditional update
guarded on the ``next_run_at`` this dispatcher observed, and only the
dispatcher whose update actually matched a row goes on to enqueue the
run. Claiming before enqueueing (rather than after) means a failure
anywhere in the cycle costs at most a missed run, never a run repeated
every minute until an operator intervenes.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import F, Value
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone
from django_q.tasks import async_task

from apps.commcare.models import RunBaseModel
from apps.exports.models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
    MultiProjectPartialExportRun,
)
from apps.forwarding.models import ForwardingConfig, ForwardingRun
from apps.refreshes.models import RefreshConfig, RefreshRun

logger = logging.getLogger(__name__)

CONFIG_MODELS = [
    ExportConfig,
    MultiProjectExportConfig,
    ForwardingConfig,
    RefreshConfig,
]

RUN_MODELS = [
    ExportRun,
    MultiProjectExportRun,
    MultiProjectPartialExportRun,
    ForwardingRun,
    RefreshRun,
]


# Added to the task timeout when computing the reaper's cutoff. started_at
# is set after Django Q2 hands the task to a worker, so the cutoff can never
# precede Django Q2's own kill on a single host — but that invariant only
# holds if the scheduler and the worker agree on the time. The margin gives
# it room to survive ordinary clock skew between hosts.
REAP_MARGIN = timedelta(seconds=60)


def reap_stale_runs():
    """Mark runs whose worker was killed as ``TIMEOUT``.

    A run is left ``STARTED`` when its worker is killed, which would
    otherwise block its config forever: ``has_active_run`` would keep
    seeing it, and the re-delivered task returns immediately because the
    run is no longer ``QUEUED``. Every runner sets ``started_at`` when it
    sets ``STARTED``, so a ``STARTED`` run older than the task timeout
    (plus ``REAP_MARGIN`` for clock skew) cannot still be running.

    ``QUEUED`` runs are deliberately not reaped: they have no
    ``started_at`` to measure from, and a run can legitimately sit queued
    for a long time behind other work.

    Returns the number of runs reaped.
    """
    now = timezone.now()
    cutoff = (
        now - timedelta(seconds=settings.Q_CLUSTER['timeout']) - REAP_MARGIN
    )
    reaped = 0
    for run_model in RUN_MODELS:
        count = run_model.objects.filter(
            status=RunBaseModel.Status.STARTED,
            started_at__lt=cutoff,
        ).update(
            status=RunBaseModel.Status.TIMEOUT,
            completed_at=now,
            # ``log`` is nullable and Concat propagates NULL, so an
            # unlogged run would otherwise lose the note entirely.
            log=Concat(
                Coalesce(F('log'), Value('')),
                Value(
                    '\n[This run timed out. Its worker was killed by Django '
                    'Q2 and the scheduler marked the run accordingly.]\n'
                ),
            ),
        )
        if count:
            logger.warning(
                'Reaped %d stale %s run(s)', count, run_model.__name__
            )
        reaped += count
    return reaped


def _advance_past(config, due_at, now):
    """The config's next run after ``due_at``, skipping any also in the past.

    Anchoring on ``due_at`` rather than ``now`` keeps a schedule on its
    original grid: an hourly schedule due at 09:00 next runs at 10:00,
    not at 10:00 plus however late the dispatcher happened to be. Runs
    that fell due while the cluster was down are skipped rather than
    replayed, so coming back up costs one run, not one per missed slot.
    """
    next_run = config.compute_next_run(due_at)
    while next_run is not None and next_run <= now:
        # compute_next_run returns a time strictly after the one passed
        # in, so this terminates.
        next_run = config.compute_next_run(next_run)
    return next_run


def run_due_schedules():
    """Enqueue a run for every scheduled config that is due.

    Each config is handled independently: a config whose schedule fields
    are malformed (e.g. an invalid timezone reaching ``compute_next_run``
    via a shell edit, ``loaddata``, or ``objects.create()`` bypassing
    validation) must not prevent the other due configs - possibly for
    other models entirely - from being enqueued.

    Stale runs are reaped first, so a config is never skipped on account
    of a run whose worker has already been killed.
    """
    reap_stale_runs()
    now = timezone.now()
    launched = []
    for config_model in CONFIG_MODELS:
        due_configs = config_model.objects.filter(
            schedule_enabled=True,
            next_run_at__lte=now,
        )
        for config in due_configs:
            try:
                next_run = _advance_past(config, config.next_run_at, now)
                # Claim the run by advancing next_run_at, conditional on it
                # still holding the value this dispatcher read. A concurrent
                # dispatcher that already claimed it matches no row here.
                claimed = config_model.objects.filter(
                    pk=config.pk, next_run_at=config.next_run_at
                ).update(next_run_at=next_run)
                if not claimed:
                    continue
                async_task(config.SCHEDULED_TASK, config.id)
            except Exception:
                # config.__str__ could itself raise on a malformed row, so
                # log by model name and pk rather than the instance.
                logger.exception(
                    'Failed to enqueue scheduled run for %s(pk=%s)',
                    config_model.__name__, config.pk,
                )
                continue
            launched.append(f'{config_model.__name__}:{config.pk}')
            logger.info(
                'Enqueued scheduled run for %s(pk=%s)',
                config_model.__name__, config.pk,
            )
    return launched
