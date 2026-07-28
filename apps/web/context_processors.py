from copy import copy
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from .failed_runs import recent_failed_runs
from .meta import absolute_url


def project_meta(request):
    # modify these values as needed and add whatever else you want globally available here
    project_data = copy(settings.PROJECT_METADATA)
    project_data['TITLE'] = '{} | {}'.format(
        project_data['NAME'],
        project_data['DESCRIPTION'],
    )
    return {
        'project_meta': project_data,
        'page_url': absolute_url(request.path),
        'page_title': '',
        'page_description': '',
        'page_image': '',
    }


def google_analytics_id(request):
    """
    Adds google analytics id to all requests
    """
    if settings.GOOGLE_ANALYTICS_ID:
        return {
            'GOOGLE_ANALYTICS_ID': settings.GOOGLE_ANALYTICS_ID,
        }
    else:
        return {}


def failed_runs_banner(request):
    """
    Surfaces recent failed runs as dismissible banner data.

    Window is failures within settings.DASHBOARD_STATS_PERIOD, further
    narrowed to failures after the session's dismissal timestamp (if any) so
    a dismissal sticks until a *new* failure occurs.
    """
    if not request.user.is_authenticated:
        return {}

    since = timezone.now() - settings.DASHBOARD_STATS_PERIOD
    dismissed_at = request.session.get('failed_runs_dismissed_at')
    if dismissed_at:
        dismissed_since = datetime.fromisoformat(dismissed_at)
        since = max(since, dismissed_since)

    data = recent_failed_runs(since)
    if not data['entries']:
        return {}
    return {'failed_runs_banner': data}
