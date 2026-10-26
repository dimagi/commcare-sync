"""
Repairs for the task queue, run by the launcher at startup.
"""

import logging

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS
from django.utils import timezone
from django_q.models import OrmQ, Schedule

# Keep in step with apps/schedules/migrations/0001_create_dispatcher_schedule.py
DISPATCHER_FUNC = 'apps.schedules.tasks.run_due_schedules'
DISPATCHER_NAME = 'Run due schedules'
DISPATCHER_MINUTES = 1

logger = logging.getLogger(__name__)


def ensure_dispatcher_schedule() -> bool:
    """
    The migration creates the schedule, but it can be deleted in the
    Django Q2 admin, and without it nothing is ever scheduled again.
    """
    if Schedule.objects.filter(func=DISPATCHER_FUNC).exists():
        return False
    Schedule.objects.create(
        func=DISPATCHER_FUNC,
        name=DISPATCHER_NAME,
        schedule_type=Schedule.MINUTES,
        minutes=DISPATCHER_MINUTES,
    )
    logger.warning('Recreated the missing dispatcher schedule')
    return True


def clear_stale_queue_locks() -> int:
    """
    The ORM broker hands out a task by setting ``lock`` to now plus
    ``retry``, and only an acknowledgement deletes the row. A task
    abandoned by a crash is invisible until ``retry`` elapses. No cluster
    is running at startup, so every lock is stale.
    """
    now = timezone.now()
    alias = settings.Q_CLUSTER.get('orm') or DEFAULT_DB_ALIAS
    cleared = OrmQ.objects.using(alias).filter(lock__gte=now).update(lock=now)
    if cleared:
        logger.warning('Cleared %s stale task queue lock(s)', cleared)
    return cleared
