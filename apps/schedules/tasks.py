"""The scheduling dispatcher.

A single django-q2 native Schedule (created by this app's migration
0001) runs ``run_due_schedules`` every minute. It enqueues a run for
every config whose ``next_run_at`` has passed and advances the config's
``next_run_at``. Overdue schedules therefore catch up with exactly one
run the next time the cluster is running.
"""

import logging

from django.utils import timezone
from django_q.tasks import async_task

logger = logging.getLogger(__name__)


def _scheduled_models():
    # Imported lazily so this module can be imported before app loading.
    from apps.exports.models import (
        ExportConfig,
        MultiProjectExportConfig,
    )
    from apps.forwarding.models import ForwardingConfig
    from apps.refreshes.models import RefreshConfig

    return [
        ExportConfig,
        MultiProjectExportConfig,
        ForwardingConfig,
        RefreshConfig,
    ]


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
    for model in _scheduled_models():
        due = model.objects.filter(
            schedule_enabled=True, next_run_at__lte=now
        )
        for config in due:
            try:
                async_task(
                    config.SCHEDULED_TASK,
                    config.id,
                    q_options=dict(config.SCHEDULED_TASK_OPTIONS),
                )
                model.objects.filter(pk=config.pk).update(
                    next_run_at=config.compute_next_run(now)
                )
            except Exception:
                # config.__str__ could itself raise on a malformed row, so
                # log by model name and pk rather than the instance.
                logger.exception(
                    'Failed to enqueue scheduled run for %s(pk=%s)',
                    model.__name__, config.pk,
                )
                continue
            launched.append(f'{model.__name__}:{config.pk}')
            logger.info(
                'Enqueued scheduled run for %s(pk=%s)',
                model.__name__, config.pk,
            )
    return launched
