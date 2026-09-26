"""System checks for the schedules app."""

from datetime import timedelta

from django.conf import settings
from django.core.checks import Error, register

from apps.schedules.tasks import REAP_MARGIN


@register()
def check_retry_outlasts_reaping(app_configs, **kwargs):
    """``Q_CLUSTER['retry']`` must be longer than the timeout plus the margin.

    ``claim_run`` retries a run whose worker died, but only if
    ``reap_stale_runs`` has marked it TIMEOUT by the time Django Q2
    delivers its task again. The reaper waits the task timeout plus
    ``REAP_MARGIN`` from when the run started, so a shorter ``retry``
    would drop every retry.
    """
    timeout = timedelta(seconds=settings.Q_CLUSTER['timeout'])
    retry = timedelta(seconds=settings.Q_CLUSTER['retry'])
    if retry > timeout + REAP_MARGIN:
        return []
    return [
        Error(
            "Q_CLUSTER['retry'] must be longer than Q_CLUSTER['timeout'] "
            'plus REAP_MARGIN.',
            hint=(
                'Otherwise a task whose worker died is delivered again '
                'before its run is reaped, and the run is never retried.'
            ),
            id='schedules.E001',
        )
    ]
