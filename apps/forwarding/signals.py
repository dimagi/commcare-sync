"""
Signal handlers for forwarding app.


How ForwardingConfig scheduling works
-------------------------------------

When a ``ForwardingConfig`` instance is created with a ``Schedule``:

1. The ``post_save`` signal is triggered.
2. The signal handler creates a Celery schedule from
   ``schedule.create_celery_schedule()``.
3. A ``PeriodicTask`` is created that calls
   ``apps.forwarding.tasks.run_forwarding_task``.
4. The ``PeriodicTask`` is linked to the ``Schedule`` model.

When Celery beat runs:

1. Celery beat checks the ``PeriodicTask`` schedule.
2. At the scheduled time, it calls
   ``run_forwarding_task(forwarding_config_id)``.
3. The task creates a ``ForwardingRun`` instance and executes
   ``run_forwarding()``.

When a ``ForwardingConfig`` instance is deleted:

1. The ``pre_delete`` signal is triggered.
2. The associated ``PeriodicTask`` is automatically deleted.

"""
import logging
from typing import Any

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django_celery_beat.models import PeriodicTask

from apps.schedules.models import Schedule
from .models import ForwardingConfig

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ForwardingConfig)
def create_or_update_periodic_task(
    sender: type[ForwardingConfig],
    instance: ForwardingConfig,
    created: bool,
    **kwargs: Any,
) -> None:
    """
    Create or update a PeriodicTask when a ForwardingConfig is saved.

    This signal handler:
    1. Creates a Celery schedule from the ForwardingConfig's schedule
    2. Creates or updates a PeriodicTask that will call run_forwarding_task
    3. Associates the PeriodicTask with the Schedule model
    """
    if not instance.schedule:
        return

    task_name = f'Run forwarding: {instance} (ID: {instance.id})'
    task_kwargs = {
        'task': 'apps.forwarding.tasks.run_scheduled_forwarding_task',
        'name': task_name,
        'enabled': True,
        'args': f'[{instance.id}]',
        'crontab': None,
        'interval': None,
    }

    celery_schedule = instance.schedule.create_celery_schedule()
    if instance.schedule.schedule_type == Schedule.ScheduleType.INTERVAL:
        task_kwargs['interval'] = celery_schedule
    else:
        task_kwargs['crontab'] = celery_schedule

    if instance.schedule.periodic_task:
        periodic_task = instance.schedule.periodic_task
        for key, value in task_kwargs.items():
            setattr(periodic_task, key, value)
        periodic_task.save()
        logger.info(f'Updated periodic task for {instance}')
    else:
        periodic_task = PeriodicTask.objects.create(**task_kwargs)
        instance.schedule.periodic_task = periodic_task
        instance.schedule.save()
        logger.info(f'Created periodic task for {instance}')


@receiver(pre_delete, sender=ForwardingConfig)
def delete_periodic_task(
    sender: type[ForwardingConfig],
    instance: ForwardingConfig,
    **kwargs: Any,
) -> None:
    """
    Delete the PeriodicTask when a ForwardingConfig is deleted.
    """
    if instance.schedule and instance.schedule.periodic_task:
        instance.schedule.periodic_task.delete()
        logger.info(f'Deleted periodic task for {instance}')
