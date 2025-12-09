"""Celery tasks for data forwarding."""
import logging

from celery import shared_task

from .models import ForwardingConfig, ForwardingRun
from .runner import run_forwarding

logger = logging.getLogger(__name__)


@shared_task
def run_forwarding_task(forwarding_config_id):
    """
    Executes a forwarding run for the given ForwardingConfig.

    :param forwarding_config_id: The ID of the ForwardingConfig to execute

    :returns: The ID of the created ForwardingRun instance
    """
    try:
        forwarding_config = ForwardingConfig.objects.get(id=forwarding_config_id)
    except ForwardingConfig.DoesNotExist:
        logger.error(
            f'ForwardingConfig {forwarding_config_id} does not exist'
        )
        return None

    forwarding_run = ForwardingRun.objects.create(
        forwarding_config=forwarding_config,
        forwarding_config_version=forwarding_config.latest_version,
        status=ForwardingRun.Status.QUEUED,
    )
    run_forwarding(forwarding_run)

    return forwarding_run.id
