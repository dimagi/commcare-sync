"""Background tasks for materialized view refreshes."""
import logging

from .models import RefreshRun
from .runner import run_refresh

logger = logging.getLogger(__name__)


def run_refresh_task(refresh_run_id):
    """
    Execute a refresh run for the given RefreshRun.
    """
    try:
        refresh_run = RefreshRun.objects.get(id=refresh_run_id)
    except RefreshRun.DoesNotExist:
        logger.error(f'RefreshRun {refresh_run_id} does not exist')
        return None

    run_refresh(refresh_run)
    return refresh_run.id
