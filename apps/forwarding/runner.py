import logging
from datetime import datetime

from django.utils import timezone
from dqf import execute_query, forward_to_api

from .models import ForwardingRun


def run_forwarding(fwd_run: ForwardingRun) -> ForwardingRun:
    """Execute a forwarding run using db-query-fwd library.

    :param fwd_run: The ForwardingRun instance to execute

    :returns: The updated ForwardingRun instance
    """
    fwd_config = fwd_run.forwarding_config
    log_lines = [
        f'{datetime.now()}: Starting forwarding for {fwd_config}',
    ]

    fwd_run.status = ForwardingRun.Status.STARTED
    fwd_run.started_at = timezone.now()
    fwd_run.save()

    try:
        db_url = fwd_config.database.connection_string
        query = fwd_config.query
        api_url = fwd_config.destination.api_url
        params = [
            p.strip()
            for p in fwd_config.query_params.splitlines()
            if p.strip()
        ]
        credentials = None
        if (
            fwd_config.destination.api_username
            and fwd_config.destination.api_password
        ):
            credentials = (
                fwd_config.destination.api_username,
                fwd_config.destination.api_password,
            )

        log_lines.append(
            f'{datetime.now()}: Executing query on {fwd_config.database}'
        )
        result = execute_query(db_url, query, params)
        log_lines.append(
            f'{datetime.now()}: Query executed successfully, '
            f'result size: {len(str(result)) if result else 0} characters'
        )

        log_lines.append(
            f'{datetime.now()}: Forwarding to {api_url}'
        )
        response = forward_to_api(api_url, result, credentials)
        log_lines.append(
            f'{datetime.now()}: Forwarded successfully, '
            f'status code: {response.status_code}'
        )
        fwd_run.status = ForwardingRun.Status.COMPLETED

    except Exception as err:
        fwd_run.status = ForwardingRun.Status.FAILED
        log_lines.append(f'{datetime.now()}: ERROR: {str(err)}')
        logging.exception('Forwarding failed')

    finally:
        fwd_run.log = '\n'.join(log_lines)
        fwd_run.completed_at = timezone.now()
        fwd_run.save()

    return fwd_run
