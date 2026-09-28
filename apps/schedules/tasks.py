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

from django.utils import timezone
from django_q.tasks import async_task

from apps.exports.models import ExportConfig, MultiProjectExportConfig
from apps.forwarding.models import ForwardingConfig
from apps.refreshes.models import RefreshConfig

logger = logging.getLogger(__name__)

CONFIG_MODELS = [
    ExportConfig,
    MultiProjectExportConfig,
    ForwardingConfig,
    RefreshConfig,
]


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
    """
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
                async_task(
                    config.SCHEDULED_TASK,
                    config.id,
                    q_options=dict(config.SCHEDULED_TASK_OPTIONS),
                )
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
