"""Background tasks for data forwarding."""
from apps.schedules.dispatch import claim_run

from .models import ForwardingRun
from .runner import run_forwarding


def run_forwarding_task(fwd_run_id):
    """
    Executes a forwarding run for the given ForwardingRun.

    :param fwd_run_id: The ID of the ForwardingRun to execute

    :returns: The ID of the ForwardingRun performed, or None if there was
        nothing to do. (See ``claim_run``.)
    """
    fwd_run = claim_run(ForwardingRun, fwd_run_id)
    if fwd_run is None:
        return None

    run_forwarding(fwd_run)
    return fwd_run.id
