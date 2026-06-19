import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from apps.db.models import Database
from apps.web.decorators import require_htmx
from commcare_sync.consts import VALID_CONFIG_PAGE_SIZES
from commcare_sync.views import (
    compute_configs_etag,
    dashboard_stats_context,
    get_config_page_size,
    get_page_from_request,
    get_run_statuses_from_request,
    paginate,
    render_config_table,
)

from .db_utils import check_connection, get_materialized_views
from .forms import RefreshConfigForm
from .models import RefreshConfig, RefreshRun
from .tasks import run_refresh_task

logger = logging.getLogger(__name__)


@login_required
def refresh_configs(request):
    """List all refresh configurations."""
    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    configs_qs = RefreshConfig.objects.order_by('-updated_at').prefetch_related(
        Prefetch('runs', queryset=RefreshRun.objects.order_by('-created_at'), to_attr='_all_runs')
    )
    page_obj = paginate(configs_qs, page_size, page_num)

    etag = compute_configs_etag(page_obj.object_list)

    return render(
        request,
        'refreshes/refresh_configs.html',
        {
            'active_tab': 'refreshes',
            'page_obj': page_obj,
            'page_size': page_size,
            'page_sizes': VALID_CONFIG_PAGE_SIZES,
            'etag': etag,
            'config_table_url': reverse('refreshes:config_table'),
            **dashboard_stats_context(),
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
    page_obj = paginate(configs_qs, page_size, page_num)
    return render_config_table(
        request,
        page_obj,
        page_size,
        'refreshes/partials/config_table.html',
        reverse('refreshes:config_table'),
    )


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

            messages.success(request, _(
                "Refresh configuration '{}' was successfully created."
            ).format(config.name))
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

            messages.success(request, _(
                "Refresh configuration '{}' was successfully updated."
            ).format(config.name))
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
        messages.success(request, _(
            "Refresh configuration '{}' was successfully deleted."
        ).format(config_name))
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
    page_obj = paginate(config.runs.order_by('-created_at'), page_size, page_num)
    return render(
        request,
        'refreshes/refresh_details.html',
        {
            'active_tab': 'refreshes',
            'config': config,
            'runs': page_obj,
            'run_history_url': reverse('refreshes:run_history_table', args=[config.id]),
            'page_size': page_size,
            'page_sizes': VALID_CONFIG_PAGE_SIZES,
        },
    )


@login_required
@require_GET
@require_htmx
def run_history_table(request, config_id):
    """HTMX endpoint to refresh the run history table."""
    config = get_object_or_404(RefreshConfig, id=config_id)
    runs_qs = config.runs.order_by('-created_at')
    statuses = get_run_statuses_from_request(request)
    runs_qs = runs_qs.filter(status__in=statuses)
    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    page_obj = paginate(runs_qs, page_size, page_num)
    return render(
        request,
        'refreshes/partials/run_history_table.html',
        {
            'config': config,
            'runs': page_obj,
            'run_history_url': reverse('refreshes:run_history_table', args=[config.id]),
            'page_size': page_size,
            'page_sizes': VALID_CONFIG_PAGE_SIZES,
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
    return HttpResponse(result.task_id)


@login_required
@require_GET
def fetch_materialized_views(request):
    """Fetch materialized views from a PostgreSQL database."""
    database_id = request.GET.get('database_id')

    if not database_id:
        return JsonResponse(
            {'error': _('database_id parameter required')},
            status=400,
        )

    try:
        database = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return JsonResponse({'error': _('Database not found')}, status=404)

    conn_str = database.connection_string
    if not conn_str.startswith('postgresql://'):
        return JsonResponse(
            {'error': _('Only PostgreSQL databases are supported')},
            status=400,
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
