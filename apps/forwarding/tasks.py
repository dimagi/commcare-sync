"""Background tasks for data forwarding."""
import logging

from .models import ForwardingRun
from .runner import run_forwarding

logger = logging.getLogger(__name__)


def run_forwarding_task(fwd_run_id):
    """
    Executes a forwarding run for the given ForwardingRun.

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
