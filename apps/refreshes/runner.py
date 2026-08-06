"""Runner for executing materialized view refreshes."""
import logging

import psycopg
from django.utils import timezone

from .db_utils import refresh_materialized_view
from .models import RefreshRun

logger = logging.getLogger(__name__)


def run_refresh(refresh_run):
    """Execute a refresh run for multiple materialized views."""
    refresh_config = refresh_run.config
    log_lines = [
        f'{timezone.now()}: Starting refresh for {refresh_config}',
        (
            f'{timezone.now()}: Refreshing '
            f'{len(refresh_config.materialized_views)} materialized view(s)'
        ),
    ]

    refresh_run.status = RefreshRun.Status.STARTED
    refresh_run.started_at = timezone.now()
    refresh_run.save()

    view_results = {}
    overall_success = True

    try:
        connection_string = refresh_config.database.connection_string

        for full_view_name in refresh_config.materialized_views:
            view_start_time = timezone.now()
            log_lines.append(
                f'{timezone.now()}: Refreshing {full_view_name}...'
            )

            try:
                if '.' in full_view_name:
                    schema_name, view_name = full_view_name.split('.', 1)
                else:
                    schema_name = 'public'
                    view_name = full_view_name

                refresh_materialized_view(
                    connection_string,
                    schema_name,
                    view_name,
                    concurrently=refresh_config.concurrently,
                )

                view_duration = (
                    timezone.now() - view_start_time
                ).total_seconds()
                view_results[full_view_name] = {
                    'status': 'success',
                    'message': 'Refresh completed successfully',
                    'duration': view_duration,
                }
                log_lines.append(
                    f'{timezone.now()}: {full_view_name} completed '
                    f'in {view_duration:.2f}s'
                )

            except psycopg.Error as view_error:
                view_duration = (
                    timezone.now() - view_start_time
                ).total_seconds()
                error_message = str(view_error)
                view_results[full_view_name] = {
                    'status': 'failed',
                    'message': error_message,
                    'duration': view_duration,
                }
                log_lines.append(
                    f'{timezone.now()}: {full_view_name} failed: '
                    f'{error_message}'
                )
                overall_success = False

        if overall_success:
            refresh_run.status = RefreshRun.Status.COMPLETED
            log_lines.append(
                f'{timezone.now()}: All views refreshed successfully'
            )
        else:
            refresh_run.status = RefreshRun.Status.FAILED
            failed_views = [
                name
                for name, result in view_results.items()
                if result['status'] == 'failed'
            ]
            log_lines.append(
                f'{timezone.now()}: Refresh completed with failures. '
                f'Failed views: {", ".join(failed_views)}'
            )

    except Exception as err:
        refresh_run.status = RefreshRun.Status.FAILED
        log_lines.append(f'{timezone.now()}: ERROR: {str(err)}')
        logger.exception('Refresh failed')

    finally:
        refresh_run.view_results = view_results
        refresh_run.log = '\n'.join(log_lines)
        refresh_run.completed_at = timezone.now()
        refresh_run.save()

    return refresh_run
