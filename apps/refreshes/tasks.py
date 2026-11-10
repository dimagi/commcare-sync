"""Background tasks for materialized view refreshes."""
from apps.schedules.dispatch import claim_run

from .models import RefreshRun
from .runner import run_refresh


def run_refresh_task(refresh_run_id):
    """
    Execute a refresh run for the given RefreshRun.

    Returns the ID of the RefreshRun performed, or None if there was
    nothing to do. (See ``claim_run``.)
    """
    refresh_run = claim_run(RefreshRun, refresh_run_id)
    if refresh_run is None:
        return None

    run_refresh(refresh_run)
    return refresh_run.id
