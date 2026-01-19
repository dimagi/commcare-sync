"""Celery tasks for data forwarding."""
import logging

from celery import shared_task

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


@shared_task
def sync_forwarding_schedules():
    """
    Syncs Schedule instances with ForwardingConfig instances.

    This task runs every 4 hours to ensure all ForwardingConfig instances
    that have a schedule also have a properly configured PeriodicTask.
    This handles cases where ForwardingConfig instances are created or
    updated outside the Django ORM (e.g., via database migrations, manual
    SQL, or other means that bypass the post_save signal).

    :returns: Dictionary with sync statistics
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

    logger.info(
        f'Forwarding schedule sync completed: {synced_count} configs synced'
    )

    return {
        'synced': synced_count,
        'total_checked': configs_with_schedule.count(),
    }
