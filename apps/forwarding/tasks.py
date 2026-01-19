"""Celery tasks for data forwarding."""
import json
import logging

from celery import shared_task
from django_celery_beat.models import PeriodicTask

from .models import ForwardingConfig, ForwardingRun
from .runner import run_forwarding
from .signals import create_or_update_periodic_task

logger = logging.getLogger(__name__)


@shared_task
def run_forwarding_task(fwd_run_id):
    """
    Executes a forwarding run for the given ForwardingRun.

    This task is used for manual runs triggered from the UI.

    :param fwd_run_id: The ID of the ForwardingRun to execute

    :returns: The ID of the ForwardingRun instance
    """
    try:
        fwd_run = ForwardingRun.objects.get(id=fwd_run_id)
    except ForwardingRun.DoesNotExist:
        logger.error(f'ForwardingRun {fwd_run_id} does not exist')
        return None

    run_forwarding(fwd_run)
    return fwd_run.id


@shared_task
def run_scheduled_forwarding_task(fwd_config_id):
    """
    Creates and executes a forwarding run for scheduled tasks.

    This task is called by Celery Beat for scheduled forwarding runs.

    :param fwd_config_id: The ID of the ForwardingConfig to execute

    :returns: The ID of the created ForwardingRun instance
    """
    try:
        fwd_config = ForwardingConfig.objects.get(id=fwd_config_id)
    except ForwardingConfig.DoesNotExist:
        logger.error(f'ForwardingConfig {fwd_config_id} does not exist')
        return None

    fwd_run = ForwardingRun.objects.create(
        forwarding_config=fwd_config,
        forwarding_config_version=fwd_config.latest_version,
        status=ForwardingRun.Status.QUEUED,
        triggered_from_ui=False,
    )
    run_forwarding(fwd_run)
    return fwd_run.id


def ensure_periodic_tasks_exist():
    """
    Ensures every ``ForwardingConfig`` instance with a schedule has
    a ``PeriodicTask``.

    :returns: Number of configs synced
    """
    configs_with_schedule = ForwardingConfig.objects.filter(
        schedule__isnull=False
    ).select_related('schedule', 'schedule__periodic_task')

    synced_count = 0

    for config in configs_with_schedule:
        create_or_update_periodic_task(
            sender=ForwardingConfig,
            instance=config,
            created=False,
        )
        synced_count += 1

    return synced_count


def delete_orphaned_periodic_tasks():
    """
    Deletes ``PeriodicTask`` instances that reference deleted
    ``ForwardingConfig`` instances.

    NOTE: This query is not efficient, as the 'task' and 'args' fields
    are not indexed in the ``PeriodicTask`` model. For large numbers of
    periodic tasks, this could be slow.

    :returns: Number of orphaned tasks deleted
    """
    orphaned_tasks = PeriodicTask.objects.filter(
        task='apps.forwarding.tasks.run_scheduled_forwarding_task'
    )

    orphaned_count = 0
    valid_config_ids = set(
        ForwardingConfig.objects.values_list('id', flat=True)
    )

    for periodic_task in orphaned_tasks:
        try:
            # periodic_task.args looks like '[config_id]'
            (config_id,) = json.loads(periodic_task.args)
        except (json.JSONDecodeError, ValueError) as err:
            logger.warning(
                f'Failed to parse args for periodic task '
                f'"{periodic_task.name}": {err}'
            )
        else:
            if config_id not in valid_config_ids:
                orphaned_count += 1
                periodic_task.delete()
                logger.info(
                    f'Deleted orphaned periodic task "{periodic_task.name}" '
                    f'for non-existent ForwardingConfig ID {config_id}'
                )

    return orphaned_count


@shared_task
def sync_forwarding_schedules():
    """
    Syncs ``Schedule`` instances with ``ForwardingConfig`` instances.

    This task runs every 4 hours to ensure all ``ForwardingConfig``
    instances that have a schedule also have a properly configured
    ``PeriodicTask``. This handles cases where ``ForwardingConfig``
    instances are created or updated outside the Django ORM (e.g. via
    database migrations, manual SQL, or other means that bypass the
    ``post_save`` signal).

    Also cleans up orphaned ``PeriodicTask`` instances that reference
    deleted ``ForwardingConfig`` instances.

    :returns: Dictionary with sync statistics
    """
    synced_count = ensure_periodic_tasks_exist()
    orphaned_count = delete_orphaned_periodic_tasks()

    logger.info(
        f'Forwarding schedule sync completed: {synced_count} configs '
        f'synced, {orphaned_count} orphaned tasks deleted'
    )

    return {
        'synced': synced_count,
        'orphaned_deleted': orphaned_count,
    }
