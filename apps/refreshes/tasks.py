"""Background tasks for materialized view refreshes."""
import logging

from apps.schedules.dispatch import create_run

from .models import RefreshConfig, RefreshRun
from .runner import run_refresh

logger = logging.getLogger(__name__)


def run_refresh_task(refresh_run_id):
    """
    Execute a refresh run for the given RefreshRun.

    Used for manual runs triggered from the UI.
    """
    try:
        refresh_run = RefreshRun.objects.get(id=refresh_run_id)
    except RefreshRun.DoesNotExist:
        logger.error(f'RefreshRun {refresh_run_id} does not exist')
        return None

    if refresh_run.status != RefreshRun.Status.QUEUED:
        # Django Q2 re-delivered a task whose run is already under way or
        # finished. Redoing the work is worse than doing nothing.
        return None

    run_refresh(refresh_run)
    return refresh_run.id


def run_scheduled_refresh_task(refresh_config_id):
    """
    Create and execute a refresh run for scheduled tasks.

    Scheduler entry point for scheduled refresh runs.
    """
    try:
        refresh_config = RefreshConfig.objects.get(id=refresh_config_id)
    except RefreshConfig.DoesNotExist:
        logger.warning(
            'run_scheduled_refresh_task: RefreshConfig %s no longer exists, '
            'skipping.',
            refresh_config_id,
        )
        return None

    refresh_run = create_run(refresh_config)
    if refresh_run is None:
        logger.info(
            'run_scheduled_refresh_task: RefreshConfig %s already has an '
            'active run, skipping.',
            refresh_config_id,
        )
        return None

    run_refresh(refresh_run)
    return refresh_run.id
