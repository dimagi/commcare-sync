"""Background tasks for data forwarding."""
import logging

from apps.schedules.dispatch import create_run

from .models import ForwardingConfig, ForwardingRun
from .runner import run_forwarding

logger = logging.getLogger(__name__)


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


def run_scheduled_forwarding_task(fwd_config_id):
    """
    Creates and executes a forwarding run for scheduled tasks.

    Scheduler entry point for scheduled forwarding runs.

    :param fwd_config_id: The ID of the ForwardingConfig to execute

    :returns: The ID of the created ForwardingRun instance
    """
    try:
        fwd_config = ForwardingConfig.objects.get(id=fwd_config_id)
    except ForwardingConfig.DoesNotExist:
        logger.warning(
            'run_scheduled_forwarding_task: ForwardingConfig %s no longer '
            'exists, skipping.',
            fwd_config_id,
        )
        return None

    fwd_run = create_run(fwd_config)
    if fwd_run is None:
        logger.info(
            'run_scheduled_forwarding_task: ForwardingConfig %s already has '
            'an active run, skipping.',
            fwd_config_id,
        )
        return None

    run_forwarding(fwd_run)
    return fwd_run.id
