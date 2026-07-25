"""
Generic signal handlers for models that inherit from ScheduleMixin.

These handlers manage the lifecycle of django-celery-beat PeriodicTask
objects. They are registered per-model in each app's signals.py via::

    from apps.schedules.signals import (
        create_or_update_periodic_task,
        delete_periodic_task,
    )
    post_save.connect(create_or_update_periodic_task, sender=MyConfig)
    pre_delete.connect(delete_periodic_task, sender=MyConfig)
"""

import json
import logging

from django_celery_beat.models import PeriodicTask

from .mixin import ScheduleMixin

logger = logging.getLogger(__name__)


def create_or_update_periodic_task(sender, instance, created, **kwargs):
    """
    Create or update a PeriodicTask when a ScheduleMixin model is saved.

    If the instance no longer has a schedule but still has a PeriodicTask,
    the orphaned PeriodicTask is cleaned up.
    """
    if not instance.has_schedule:
        if instance.periodic_task:
            instance.periodic_task.delete()
            # Use QuerySet.update() rather than instance.save() to avoid
            # triggering this post_save signal recursively.
            sender.objects.filter(pk=instance.pk).update(periodic_task=None)
            logger.info(
                f'Deleted periodic task for {instance} (schedule removed)'
            )
        return

    for attr in ('SCHEDULED_TASK', 'PERIODIC_TASK_PREFIX'):
        if not isinstance(getattr(instance, attr, None), str):
            raise TypeError(
                f'{type(instance).__name__} must define {attr} as a string '
                'class attribute'
            )

    task_name = (
        f'{instance.PERIODIC_TASK_PREFIX}: {instance} (ID: {instance.id})'
    )
    task_kwargs = {
        'task': instance.SCHEDULED_TASK,
        'name': task_name,
        'args': json.dumps([instance.id]),
        'crontab': None,
        'interval': None,
    }

    celery_schedule = instance.create_celery_schedule()
    if instance.schedule_type == ScheduleMixin.ScheduleType.INTERVAL:
        task_kwargs['interval'] = celery_schedule
    else:
        task_kwargs['crontab'] = celery_schedule

    if instance.periodic_task:
        periodic_task = instance.periodic_task
        for key, value in task_kwargs.items():
            setattr(periodic_task, key, value)
        periodic_task.save()
        logger.info(f'Updated periodic task for {instance}')
    else:
        # If `instance` already has a PeriodicTask, preserve its value
        # of `enabled` so that a manually-paused task is not silently
        # re-enabled. Default to `True`
        task_kwargs['enabled'] = True
        periodic_task = PeriodicTask.objects.create(**task_kwargs)
        # Use QuerySet.update() rather than instance.save() to avoid
        # triggering this post_save signal recursively.
        sender.objects.filter(pk=instance.pk).update(
            periodic_task=periodic_task
        )
        logger.info(f'Created periodic task for {instance}')


def delete_periodic_task(sender, instance, **kwargs):
    """Delete the PeriodicTask when a ScheduleMixin model is deleted."""
    if instance.periodic_task:
        instance.periodic_task.delete()
        logger.info(f'Deleted periodic task for {instance}')
