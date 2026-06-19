import hashlib

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.commcare.models import RunBaseModel
from apps.web.stats import (
    _get_export_statistics,
    _get_forwarding_statistics,
    _get_refresh_statistics,
)
from apps.web.templatetags.dateformat_tags import readable_timedelta
from commcare_sync.consts import VALID_CONFIG_PAGE_SIZES


def get_ui_page_size(request):
    limit = settings.COMMCARE_SYNC_UI_PAGE_SIZE
    if 'limit' in request.GET:
        try:
            limit = int(request.GET['limit'])
        except ValueError:
            pass
    return limit


def get_hide_skipped_from_request(request):
    if 'hide_skipped' in request.GET:
        return request.GET['hide_skipped'] == 'y'
    return False


def get_config_page_size(request):
    if 'page_size' in request.GET:
        try:
            size = int(request.GET['page_size'])
            if size in VALID_CONFIG_PAGE_SIZES:
                return size
        except ValueError:
            pass
    return VALID_CONFIG_PAGE_SIZES[0]


def get_page_from_request(request):
    try:
        return max(int(request.GET.get('page', 1)), 1)
    except ValueError:
        return 1


def paginate(object_list, page_size, page_num):
    """Return the requested page, clamping past-the-end requests to the last page."""
    paginator = Paginator(object_list, page_size)
    try:
        return paginator.page(page_num)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def dashboard_stats_context():
    """Template context for the cross-app dashboard statistics shown on each config list page."""
    now = timezone.now()
    period = settings.DASHBOARD_STATS_PERIOD
    current_start = now - period
    previous_start = current_start - period
    return {
        'stats_period': readable_timedelta(period, short=True),
        'export_stats': _get_export_statistics(current_start, previous_start),
        'refresh_stats': _get_refresh_statistics(current_start, previous_start),
        'forwarding_stats': _get_forwarding_statistics(current_start, previous_start),
    }


# Per-run statuses available for filtering. RunBaseModel.Status is the shared base
# enum (queued/started/completed/failed/skipped); ExportRunBase additionally
# defines MULTIPLE — an aggregate for multi-project parent runs — which is
# deliberately not a per-run filter state, so deriving from the base excludes it.
_VALID_RUN_STATUSES = set(RunBaseModel.Status.values)


def get_run_statuses_from_request(request):
    """
    Returns a list of statuses to filter runs by.

    Show only runs whose status is in the list. (If the list is empty,
    show nothing.)
    """
    return [
        s for s in request.GET.getlist('status_filter')
        if s in _VALID_RUN_STATUSES
    ]


def compute_configs_etag(configs_list):
    """
    Returns MD5 fingerprint of (run.id, created_at, status) for each
    config's latest run.
    """
    parts = []
    for config in configs_list:
        all_runs = getattr(config, '_all_runs', None)
        run = all_runs[0] if all_runs else None
        if run:
            parts.append(f'{run.id}:{run.created_at.isoformat()}:{run.status}')
        else:
            parts.append(f'config:{config.id}:no-runs')
    return hashlib.md5('|'.join(parts).encode()).hexdigest()


def render_config_table(request, page_obj, page_size, template, config_table_url):
    """Render a config table partial, returning an empty no-swap response when the ETag is unchanged."""
    etag = compute_configs_etag(page_obj.object_list)
    if request.GET.get('etag') == etag:
        response = HttpResponse()
        response['HX-Reswap'] = 'none'
        return response

    return render(request, template, {
        'page_obj': page_obj,
        'page_size': page_size,
        'page_sizes': VALID_CONFIG_PAGE_SIZES,
        'etag': etag,
        'config_table_url': config_table_url,
    })
