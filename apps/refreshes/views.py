import hashlib
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, Paginator
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from apps.db.models import Database
from apps.web.stats import (
    _get_export_statistics,
    _get_forwarding_statistics,
    _get_refresh_statistics,
)
from apps.web.templatetags.dateformat_tags import readable_timedelta
from commcare_sync.views import (
    get_config_page_size,
    get_page_from_request,
    get_run_statuses_from_request,
)

from .db_utils import check_connection, get_materialized_views
from .forms import RefreshConfigForm
from .models import RefreshConfig, RefreshRun
from .tasks import run_refresh_task

logger = logging.getLogger(__name__)


def _compute_refresh_etag(configs_list):
    parts = []
    for config in configs_list:
        # Use prefetched _all_runs if available, else DB query
        all_runs = getattr(config, '_all_runs', None)
        run = all_runs[0] if all_runs else config.runs.order_by('-created_at').first()
        if run:
            parts.append(f"{run.id}:{run.created_at.isoformat()}:{run.status}")
        else:
            parts.append(f"config:{config.id}:no-runs")
    return hashlib.md5('|'.join(parts).encode()).hexdigest()


@login_required
def refresh_configs(request):
    """List all refresh configurations."""
    now = timezone.now()
    period = settings.DASHBOARD_STATS_PERIOD
    current_start = now - period
    previous_start = current_start - period

    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    configs_qs = RefreshConfig.objects.order_by('-updated_at').prefetch_related(
        Prefetch('runs', queryset=RefreshRun.objects.order_by('-created_at'), to_attr='_all_runs')
    )
    paginator = Paginator(configs_qs, page_size)
    try:
        page_obj = paginator.page(page_num)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    etag = _compute_refresh_etag(page_obj.object_list)

    return render(
        request,
        'refreshes/refresh_configs.html',
        {
            'active_tab': 'refreshes',
            'configs': page_obj,
            'page_size': page_size,
            'page_sizes': [10, 20, 50],
            'etag': etag,
            'stats_period': readable_timedelta(period, short=True),
            'export_stats': _get_export_statistics(current_start, previous_start),
            'refresh_stats': _get_refresh_statistics(current_start, previous_start),
            'forwarding_stats': _get_forwarding_statistics(current_start, previous_start),
        },
    )


@login_required
@require_GET
def config_table(request):
    """HTMX endpoint: paginated + ETag-guarded refresh config table partial."""
    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    configs_qs = RefreshConfig.objects.order_by('-updated_at').prefetch_related(
        Prefetch('runs', queryset=RefreshRun.objects.order_by('-created_at'), to_attr='_all_runs')
    )
    paginator = Paginator(configs_qs, page_size)
    try:
        page_obj = paginator.page(page_num)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    etag = _compute_refresh_etag(page_obj.object_list)
    if request.GET.get('etag') == etag:
        response = HttpResponse()
        response['HX-Reswap'] = 'none'
        return response

    return render(request, 'refreshes/partials/config_table.html', {
        'configs': page_obj,
        'page_size': page_size,
        'page_sizes': [10, 20, 50],
        'etag': etag,
    })


@login_required
@require_GET
def run_log(request, run_id):
    """HTMX endpoint: log fragment for a RefreshRun."""
    run = get_object_or_404(RefreshRun, id=run_id)
    return render(request, 'refreshes/partials/run_log.html', {'run': run})


@login_required
def create_refresh_config(request):
    """Create a new refresh configuration."""
    if request.method == 'POST':
        config_form = RefreshConfigForm(request.POST)

        if config_form.is_valid():
            with transaction.atomic():
                config = config_form.save()

            messages.success(
                request,
                _(
                    'Refresh configuration "{}" was successfully created.'
                ).format(config.name),
            )
            return HttpResponseRedirect(
                reverse('refreshes:refresh_details', args=[config.id])
            )
    else:
        config_form = RefreshConfigForm()

    return render(
        request,
        'refreshes/create_refresh_config.html',
        {
            'active_tab': 'create_refresh',
            'config_form': config_form,
        },
    )


@login_required
def edit_refresh_config(request, config_id):
    """Edit an existing refresh configuration."""
    config = get_object_or_404(RefreshConfig, id=config_id)

    if request.method == 'POST':
        config_form = RefreshConfigForm(request.POST, instance=config)

        if config_form.is_valid():
            with transaction.atomic():
                config_form.save()

            messages.success(
                request,
                _(
                    'Refresh configuration "{}" was successfully updated.'
                ).format(config.name),
            )
            return HttpResponseRedirect(
                reverse('refreshes:refresh_details', args=[config.id])
            )
    else:
        config_form = RefreshConfigForm(instance=config)

    return render(
        request,
        'refreshes/edit_refresh_config.html',
        {
            'active_tab': 'refreshes',
            'config_form': config_form,
            'config': config,
        },
    )


@login_required
def delete_refresh_config(request, config_id):
    """Delete an existing refresh configuration."""
    config = get_object_or_404(RefreshConfig, id=config_id)

    if request.method == 'POST':
        config_name = config.name
        config.delete()
        messages.success(
            request,
            _('Refresh configuration "{}" was successfully deleted.').format(
                config_name
            ),
        )
        return HttpResponseRedirect(reverse('refreshes:refresh_configs'))

    return render(
        request,
        'refreshes/delete_refresh_config.html',
        {
            'active_tab': 'refreshes',
            'config': config,
        },
    )


@login_required
def refresh_details(request, config_id):
    """Display details for a refresh configuration."""
    config = get_object_or_404(RefreshConfig, id=config_id)
    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    paginator = Paginator(config.runs.order_by('-created_at'), page_size)
    try:
        page_obj = paginator.page(page_num)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return render(
        request,
        'refreshes/refresh_details.html',
        {
            'active_tab': 'refreshes',
            'config': config,
            'runs': page_obj,
            'run_history_url': reverse('refreshes:run_history_table', args=[config.id]),
            'page_size': page_size,
            'page_sizes': [10, 20, 50],
        },
    )


@login_required
@require_GET
def run_history_table(request, config_id):
    """HTMX endpoint to refresh the run history table."""
    config = get_object_or_404(RefreshConfig, id=config_id)
    runs_qs = config.runs.order_by('-created_at')
    statuses = get_run_statuses_from_request(request)
    if statuses is not None:
        runs_qs = runs_qs.filter(status__in=statuses)
    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    paginator = Paginator(runs_qs, page_size)
    try:
        page_obj = paginator.page(page_num)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return render(
        request,
        'refreshes/partials/run_history_table.html',
        {
            'config': config,
            'runs': page_obj,
            'run_history_url': reverse('refreshes:run_history_table', args=[config.id]),
            'page_size': page_size,
            'page_sizes': [10, 20, 50],
        },
    )


@login_required
@require_POST
def run_refresh(request, config_id):
    """Manually trigger a refresh run."""
    config = get_object_or_404(RefreshConfig, id=config_id)

    refresh_run = RefreshRun.objects.create(
        refresh_config=config,
        refresh_config_version=config.latest_version,
        triggered_from_ui=True,
        triggered_by=request.user,
    )

    result = run_refresh_task.delay(refresh_run.id)
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)
    return HttpResponse(result.task_id)


@login_required
@require_GET
def fetch_materialized_views(request):
    """Fetch materialized views from a PostgreSQL database."""
    database_id = request.GET.get('database_id')

    if not database_id:
        return JsonResponse(
            {'error': 'database_id parameter required'}, status=400
        )

    try:
        database = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return JsonResponse({'error': 'Database not found'}, status=404)

    conn_str = database.connection_string
    if not conn_str.startswith('postgresql://'):
        return JsonResponse(
            {'error': 'Only PostgreSQL databases are supported'}, status=400
        )

    try:
        success, message = check_connection(conn_str)
        if not success:
            return JsonResponse(
                {'error': _('An error occurred connecting to the database.')},
                status=500,
            )

        views = get_materialized_views(conn_str)
        return JsonResponse({'views': views})

    except Exception:
        logger.exception('Error fetching materialized views')
        return JsonResponse(
            {'error': _('An error occurred fetching materialized views.')},
            status=500,
        )
