"""The scheduling dispatcher.

A Django Q2 Schedule runs ``run_due_schedules`` every minute. (See
``apps/schedules/migrations/0001_create_dispatcher_schedule.py``.) It
enqueues a run for every config whose ``next_run_at`` has passed and
advances the config's ``next_run_at``. This way overdue schedules catch
up with exactly one run the next time the cluster is running.

Advancing ``next_run_at`` is a *reservation*: it is a conditional update
guarded on the ``next_run_at`` this dispatcher observed, and only the
dispatcher whose update actually matched a row goes on to enqueue the
run. Reserving before enqueueing (rather than after) means a failure
anywhere in the cycle costs at most a missed run, never a run repeated
every minute until an operator intervenes.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import F, Value
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone

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
from apps.schedules.dispatch import create_run_and_dispatch

logger = logging.getLogger(__name__)

CONFIG_MODELS = [
    ExportConfig,
    MultiProjectExportConfig,
    ForwardingConfig,
    RefreshConfig,
]

# Every concrete run model. `test_run_models_lists_every_concrete_run_model` in
# `apps/schedules/tests/test_reap_stale_runs.py` checks that none are missing.
RUN_MODELS = [
    ExportRun,
    MultiProjectExportRun,
    # Blocks nothing, because its parent run carries the config's active
    # state. It is reaped so that run history doesn't show a dead partial
    # run as running.
    MultiProjectPartialExportRun,
    ForwardingRun,
    RefreshRun,
]


# Added to the task timeout when computing the reaper's cutoff.
REAP_MARGIN = timedelta(seconds=60)


def reap_stale_runs():
    """Mark runs whose worker was killed or timed out as ``TIMEOUT``.

    A run is left ``STARTED`` when its worker dies (OOM, SIGKILL, a
    reboot), and also when Django Q2 stops it at the timeout. Those
    would block its config forever, because ``has_active_run`` would
    keep seeing it. ``apps.schedules.dispatch.claim_run`` sets
    ``started_at`` when it sets the status of a run to ``STARTED``, so a
    ``STARTED`` run older than the task timeout (plus ``REAP_MARGIN``)
    cannot still be running.

    ``QUEUED`` runs are deliberately not reaped: they have no
    ``started_at`` to measure from, and a run can legitimately sit
    queued for a long time behind other work.

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
                    '\n[This run did not finish. It exceeded the time '
                    'limit, or its worker stopped unexpectedly.]\n'
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
    of a run whose worker has already been killed. Reaping is
    housekeeping: if it fails, the failure is logged and due configs are
    still enqueued.
    """
    try:
        reap_stale_runs()
    except Exception:
        logger.exception('Failed to reap stale runs')
    now = timezone.now()
    launched = []
    for config_model in CONFIG_MODELS:
        due_configs = config_model.objects.filter(
            schedule_enabled=True,
            next_run_at__lte=now,
        )
        for config in due_configs:
            if _dispatch_due_config(config_model, config, now):
                launched.append(f'{config_model.__name__}:{config.pk}')
    return launched


def _dispatch_due_config(config_model, config, now):
    """Dispatch a run for ``config``, which is due. Return whether it did.

    Any error is logged rather than raised, so that one malformed config
    doesn't stop the dispatcher from handling the rest.
    """
    try:
        next_run = _advance_past(config, config.next_run_at, now)
        # Reserve the slot by advancing next_run_at, conditional on it
        # still holding the value this dispatcher read. A concurrent
        # dispatcher that already reserved it matches no row here.
        reserved = config_model.objects.filter(
            pk=config.pk, next_run_at=config.next_run_at
        ).update(next_run_at=next_run)
        if not reserved:
            return False
        run = create_run_and_dispatch(config, triggered_from_ui=False)
    except Exception:
        # config.__str__ could itself raise on a malformed row, so log by
        # model name and pk rather than the instance.
        logger.exception(
            'Failed to enqueue scheduled run for %s(pk=%s)',
            config_model.__name__, config.pk,
        )
        return False
    if run is None:
        # The slot is lost, not deferred: next_run_at has already moved
        # on.
        logger.info(
            'Skipped scheduled run for %s(pk=%s): it already has an active '
            'run',
            config_model.__name__, config.pk,
        )
        return False
    logger.info(
        'Enqueued scheduled run for %s(pk=%s)',
        config_model.__name__, config.pk,
    )
    return True
