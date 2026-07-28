"""Background tasks for materialized view refreshes."""
import logging

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
        # The task was redelivered — most likely by a restart clearing the
        # queue lock — after the run reached a terminal status. Re-running it
        # would resurrect a run that history already reports as finished.
        logger.info(
            f'Skipping RefreshRun {refresh_run_id}: '
            f'status is {refresh_run.status}, not queued'
        )
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
        logger.error(f'RefreshConfig {refresh_config_id} does not exist')
        return None

    if refresh_config.runs.filter(
        status__in=[
            RefreshRun.Status.QUEUED,
            RefreshRun.Status.STARTED,
        ]
    ).exists():
        logger.info(
            f'Skipping scheduled refresh for {refresh_config} - '
            f'already has queued or running run'
        )
        return None

    refresh_run = RefreshRun.objects.create(
        refresh_config=refresh_config,
        refresh_config_version=refresh_config.latest_version,
        status=RefreshRun.Status.QUEUED,
        triggered_from_ui=False,
    )
    run_refresh(refresh_run)
    return refresh_run.id
