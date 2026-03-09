"""
Signal handlers for models that use a Schedule.

These handlers manage the lifecycle of django-celery-beat PeriodicTask
objects. They are registered per-model in each app's signals.py via::

    from apps.schedules.signals import (
        create_or_update_periodic_task,
        delete_periodic_task,
    )
    post_save.connect(create_or_update_periodic_task, sender=MyConfig)
    pre_delete.connect(delete_periodic_task, sender=MyConfig)
"""
import logging

from django_celery_beat.models import PeriodicTask

from apps.schedules.models import Schedule

logger = logging.getLogger(__name__)


def create_or_update_periodic_task(sender, instance, created, **kwargs):
    """
    Create or update a PeriodicTask when a model with a Schedule is saved.

    This signal handler:
    1. Creates a Celery schedule from the instance's schedule
    2. Creates or updates a PeriodicTask that will call the configured task
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


def delete_periodic_task(sender, instance, **kwargs):
    """Delete the PeriodicTask when a model with a Schedule is deleted."""
    if instance.schedule and instance.schedule.periodic_task:
        instance.schedule.periodic_task.delete()
        logger.info(f'Deleted periodic task for {instance}')
