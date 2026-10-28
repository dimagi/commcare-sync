from django import template
from django.conf import settings
from django.utils import timezone

from apps.web.failed_runs import dismissed_since, recent_failed_runs

register = template.Library()


@register.inclusion_tag(
    'web/components/failed_runs_banner.html', takes_context=True
)
def failed_runs_banner(context):
    """
    The runs that failed or were interrupted recently, for signed-in
    users, less those seen when the banner was last dismissed. A
    template tag rather than a context processor, so that HTMX partials,
    which are rendered often, never pay for the queries.
    """
    request = context['request']
    if not request.user.is_authenticated:
        return {'failed_runs': None}
    since = timezone.now() - settings.DASHBOARD_STATS_PERIOD
    dismissed_at = dismissed_since(request.session)
    if dismissed_at is not None:
        since = max(since, dismissed_at)
    return {'failed_runs': recent_failed_runs(since)}
