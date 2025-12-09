import logging
from datetime import datetime

from django.utils import timezone
from dqf import execute_query, forward_to_api

from .models import ForwardingRun


def run_forwarding(forwarding_run: ForwardingRun) -> ForwardingRun:
    """Execute a forwarding run using db-query-fwd library.

    :param forwarding_run: The ForwardingRun instance to execute

    :returns: The updated ForwardingRun instance
    """
    forwarding_config = forwarding_run.forwarding_config
    forwarding_run.status = ForwardingRun.Status.STARTED
    forwarding_run.started_at = timezone.now()
    forwarding_run.save()

    log_lines = []

    try:
        db_url = forwarding_config.database.connection_string
        query = forwarding_config.query
        api_url = forwarding_config.destination.api_url

        params = [
            p.strip()
            for p in forwarding_config.query_params.splitlines()
            if p.strip()
        ]

        credentials = None
        if (
            forwarding_config.destination.api_username
            and forwarding_config.destination.api_password
        ):
            credentials = (
                forwarding_config.destination.api_username,
                forwarding_config.destination.api_password,
            )

        log_lines.append(
            f'{datetime.now()}: Starting forwarding for {forwarding_config.name}'
        )
        log_lines.append(
            f'{datetime.now()}: Executing query on {forwarding_config.database.name}'
        )

        result = execute_query(db_url, query, params)

        log_lines.append(
            f'{datetime.now()}: Query executed successfully, '
            f'result size: {len(str(result)) if result else 0} characters'
        )
        log_lines.append(f'{datetime.now()}: Forwarding to {api_url}')

        response = forward_to_api(api_url, result, credentials)

        log_lines.append(
            f'{datetime.now()}: Forwarded successfully, '
            f'status code: {response.status_code}'
        )

        forwarding_run.status = ForwardingRun.Status.COMPLETED

    except Exception as err:
        forwarding_run.status = ForwardingRun.Status.FAILED
        log_lines.append(f'{datetime.now()}: ERROR: {str(err)}')
        logging.exception('Forwarding failed')

    finally:
        forwarding_run.log = '\n'.join(log_lines)
        forwarding_run.completed_at = timezone.now()
        forwarding_run.save()

    return forwarding_run
