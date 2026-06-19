import hashlib
import json
import logging
import os
from itertools import chain

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, Page, Paginator
from django.db.models import Max, Prefetch
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET, require_POST
from reversion.models import Version

from apps.commcare.models import CommCareAccount, CommCareProject
from apps.web.decorators import admin_required, require_htmx
from apps.web.stats import (
    _get_export_statistics,
    _get_forwarding_statistics,
    _get_refresh_statistics,
)
from apps.web.templatetags.dateformat_tags import readable_timedelta
from commcare_sync.consts import VALID_CONFIG_PAGE_SIZES
from commcare_sync.views import (
    get_config_page_size,
    get_page_from_request,
    get_run_statuses_from_request,
    get_ui_page_size,
)

from .api_client import fetch_available_configs
from .forms import (
    ExportConfigForm,
    MultiProjectExportConfigForm,
)
from .models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)
from .tasks import run_export_task, run_multi_project_export_task

logger = logging.getLogger(__name__)


def _merged_export_configs(page_size: int, page_num: int) -> Page:
    """Return a Page object combining ExportConfig and MultiProjectExportConfig."""
    single = (
        ExportConfig.objects
        .select_related('project')
        .annotate(last_run_at=Max('runs__created_at'))
        .prefetch_related(Prefetch(
            'runs',
            queryset=ExportRun.objects.order_by('-created_at'),
            to_attr='_all_runs',
        ))
    )
    multi = (
        MultiProjectExportConfig.objects
        .annotate(last_run_at=Max('runs__created_at'))
        .prefetch_related(Prefetch(
            'runs',
            queryset=MultiProjectExportRun.objects.order_by('-created_at'),
            to_attr='_all_runs',
        ))
    )
    all_configs = sorted(
        chain(single, multi),
        key=lambda c: c.last_run_at or c.updated_at,  # type: ignore[attr-defined]
        reverse=True,
    )
    paginator = Paginator(all_configs, page_size)
    try:
        return paginator.page(page_num)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def _compute_exports_etag(configs_list):
    """MD5 fingerprint of (run.id, created_at, status) for each config's latest run."""
    parts = []
    for config in configs_list:
        all_runs = getattr(config, '_all_runs', None)
        run = all_runs[0] if all_runs else None
        if run:
            parts.append(f'{run.id}:{run.created_at.isoformat()}:{run.status}')
        else:
            parts.append(f'config:{config.id}:no-runs')
    return hashlib.md5('|'.join(parts).encode()).hexdigest()


@login_required
def home(request):
    now = timezone.now()
    period = settings.DASHBOARD_STATS_PERIOD
    current_start = now - period
    previous_start = current_start - period

    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    page_obj = _merged_export_configs(page_size, page_num)
    etag = _compute_exports_etag(page_obj.object_list)

    return render(request, 'exports/exports_home.html', {
        'active_tab': 'exports',
        'page_obj': page_obj,
        'page_size': page_size,
        'page_sizes': VALID_CONFIG_PAGE_SIZES,
        'etag': etag,
        'config_table_url': reverse('exports:config_table'),
        'stats_period': readable_timedelta(period, short=True),
        'export_stats': _get_export_statistics(current_start, previous_start),
        'refresh_stats': _get_refresh_statistics(current_start, previous_start),
        'forwarding_stats': _get_forwarding_statistics(current_start, previous_start),
    })


@login_required
@require_GET
def config_table(request):
    """HTMX endpoint: paginated + ETag-guarded exports config table partial."""
    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    page_obj = _merged_export_configs(page_size, page_num)

    etag = _compute_exports_etag(page_obj.object_list)
    if request.GET.get('etag') == etag:
        response = HttpResponse()
        response['HX-Reswap'] = 'none'
        return response

    return render(
        request,
        'exports/partials/config_table.html',
        {
            'page_obj': page_obj,
            'page_size': page_size,
            'page_sizes': VALID_CONFIG_PAGE_SIZES,
            'etag': etag,
            'config_table_url': reverse('exports:config_table'),
        },
    )


@login_required
@require_GET
def run_log(request, run_id):
    """HTMX endpoint: log fragment for an ExportRun."""
    run = get_object_or_404(ExportRun, id=run_id)
    return render(request, 'exports/partials/run_log.html', {'run': run})


@login_required
@require_GET
def multi_run_log(request, run_id):
    """HTMX endpoint: log fragment for a MultiProjectExportRun."""
    run = get_object_or_404(MultiProjectExportRun, id=run_id)
    return render(request, 'exports/partials/run_log.html', {'run': run})


@login_required
def create_export_config(request):

    if request.method == 'POST':
        config_form = ExportConfigForm(request.POST, request.FILES)
        if config_form.is_valid():
            export = config_form.save()
            messages.success(request, _(
                "Export '{}' was successfully created."
            ).format(export.name))
            return HttpResponseRedirect(
                reverse('exports:export_details', args=[export.id])
            )
    else:
        config_form = ExportConfigForm()

    return render(
        request,
        'exports/create_export.html',
        {
            'active_tab': 'create_export',
            'config_form': config_form,
        },
    )


@login_required
def create_multi_export_config(request):
    if request.method == 'POST':
        config_form = MultiProjectExportConfigForm(request.POST, request.FILES)
        if config_form.is_valid():
            export = config_form.save()
            config_form.save_m2m()
            messages.success(request, _(
                "Export '{}' was successfully created."
            ).format(export.name))
            return HttpResponseRedirect(
                reverse('exports:multi_export_details', args=[export.id])
            )
    else:
        config_form = MultiProjectExportConfigForm()

    return render(
        request,
        'exports/create_multi_project_export.html',
        {
            'active_tab': 'create_multi_export',
            'config_form': config_form,
        },
    )


@login_required
def edit_export_config(request, export_id):
    export = get_object_or_404(ExportConfig, id=export_id)
    if request.method == 'POST':
        config_form = ExportConfigForm(
            request.POST,
            request.FILES,
            instance=export,
        )
        if config_form.is_valid():
            export = config_form.save()
            messages.success(request, _(
                "Export '{}' was successfully saved."
            ).format(export.name))
            return HttpResponseRedirect(
                reverse('exports:export_details', args=[export.id])
            )
    else:
        config_form = ExportConfigForm(instance=export)

    return render(
        request,
        'exports/edit_export.html',
        {
            'active_tab': 'exports',
            'config_form': config_form,
            'export': export,
        },
    )


@login_required
def edit_multi_export_config(request, export_id):
    export = get_object_or_404(MultiProjectExportConfig, id=export_id)
    if request.method == 'POST':
        config_form = MultiProjectExportConfigForm(
            request.POST, request.FILES, instance=export
        )
        if config_form.is_valid():
            export = config_form.save()
            messages.success(request, _(
                "Export '{}' was successfully saved."
            ).format(export.name))
            return HttpResponseRedirect(
                reverse('exports:multi_export_details', args=[export.id])
            )
    else:
        config_form = MultiProjectExportConfigForm(instance=export)

    return render(
        request,
        'exports/edit_multi_project_export.html',
        {
            'active_tab': 'create_multi_export',
            'config_form': config_form,
        },
    )


@login_required
def delete_export_config(request, export_id):
    export = get_object_or_404(ExportConfig, id=export_id)
    if request.method == 'POST':
        export.delete()
        messages.success(request, _(
            "Export file '{}' was successfully deleted."
        ).format(export.name))
        return HttpResponseRedirect(reverse('exports:home'))
    return render(
        request,
        'exports/delete_export.html',
        {
            'active_tab': 'exports',
            'export': export,
        },
    )


@login_required
def delete_multi_export_config(request, export_id):
    export = get_object_or_404(MultiProjectExportConfig, id=export_id)
    if request.method == 'POST':
        export.delete()
        messages.success(request, _(
            "Export file '{}' was successfully deleted."
        ).format(export.name))
        return HttpResponseRedirect(reverse('exports:home'))
    return render(
        request,
        'exports/delete_export.html',
        {
            'active_tab': 'exports',
            'export': export,
        },
    )


@login_required
def export_details(request, export_id):
    export = get_object_or_404(ExportConfig, id=export_id)
    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    paginator = Paginator(export.runs.order_by('-created_at'), page_size)
    try:
        page_obj = paginator.page(page_num)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return render(
        request,
        'exports/export_details.html',
        {
            'active_tab': 'exports',
            'export': export,
            'runs': page_obj,
            'run_history_url': reverse('exports:run_history_table', args=[export.id]),
            'page_size': page_size,
            'page_sizes': VALID_CONFIG_PAGE_SIZES,
        },
    )


@login_required
@require_GET
@require_htmx
def run_history_table(request, export_id):
    """HTMX endpoint to refresh the run history table."""
    export = get_object_or_404(ExportConfig, id=export_id)
    is_multi_project = request.GET.get('is_multi_project') == 'true'
    runs_qs = export.runs.order_by('-created_at')
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
    run_history_url = reverse('exports:run_history_table', args=[export.id])
    if is_multi_project:
        run_history_url += '?is_multi_project=true'
    return render(
        request,
        'exports/partials/run_history_table.html',
        {
            'export': export,
            'runs': page_obj,
            'is_multi_project': is_multi_project,
            'run_history_url': run_history_url,
            'page_size': page_size,
            'page_sizes': VALID_CONFIG_PAGE_SIZES,
        },
    )


@login_required
def download_export_file(request, export_id):
    export = get_object_or_404(ExportConfig, id=export_id)
    return _download_config_file(export.config_file)


@login_required
def download_multi_export_file(request, export_id):
    export = get_object_or_404(MultiProjectExportConfig, id=export_id)
    return _download_config_file(export.config_file)


@login_required
def download_export_file_version(request, version_id):
    version = get_object_or_404(Version, id=version_id)
    return _download_config_file(version.field_dict['config_file'])


def _download_config_file(export_file_field):
    response = HttpResponse(
        export_file_field.read(),
        content_type='application/force-download',
    )
    response['Content-Disposition'] = (
        f'attachment; filename={os.path.basename(export_file_field.name)}'
    )
    return response


@login_required
def multi_export_details(request, export_id):
    export = get_object_or_404(MultiProjectExportConfig, id=export_id)
    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    paginator = Paginator(export.runs.order_by('-created_at'), page_size)
    try:
        page_obj = paginator.page(page_num)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    run_history_url = (
        reverse('exports:run_history_table', args=[export.id])
        + '?is_multi_project=true'
    )
    return render(
        request,
        'exports/multi_project_export_details.html',
        {
            'active_tab': 'exports',
            'export': export,
            'runs': page_obj,
            'run_history_url': run_history_url,
            'page_size': page_size,
            'page_sizes': VALID_CONFIG_PAGE_SIZES,
        },
    )


@login_required
def multi_export_run_details(request, export_id, run_id):
    export_run = get_object_or_404(MultiProjectExportRun, id=run_id)
    if export_run.base_export_config.id != export_id:
        raise Http404(
            f'Export id {export_id} did not match run value of '
            f'{export_run.base_export_config.id}!'
        )
    return render(
        request,
        'exports/multi_project_export_run_details.html',
        {
            'active_tab': 'exports',
            'export_run': export_run,
            'export': export_run.base_export_config,
            'runs': export_run.partial_runs.order_by('-created_at')[
                : get_ui_page_size(request)
            ],
        },
    )


@login_required
@require_POST
def run_export(request, export_id):
    export = get_object_or_404(ExportConfig, id=export_id)

    options = json.loads(request.body)
    force_sync = options.get('forceSync', False)
    export_record = ExportRun.objects.create(
        base_export_config=export,
        export_config_version=export.latest_version,
        triggered_from_ui=True,
        triggered_by=request.user,
    )

    result = run_export_task.delay(
        export_record.id,
        force_sync_all_data=force_sync,
    )
    return HttpResponse(result.task_id)


@login_required
@require_POST
def run_multi_export(request, export_id):
    export = get_object_or_404(MultiProjectExportConfig, id=export_id)

    options = json.loads(request.body)
    force_sync = options.get('forceSync', False)
    export_record = MultiProjectExportRun.objects.create(
        base_export_config=export,
        export_config_version=export.latest_version,
        triggered_from_ui=True,
        triggered_by=request.user,
    )

    result = run_multi_project_export_task.delay(
        export_record.id,
        force_sync_all_data=force_sync,
    )
    return HttpResponse(result.task_id)


@login_required
def fetch_config_files(request):
    """
    HTMX endpoint to fetch available config files from CommCare HQ.

    Expects GET parameters ``account`` and ``project`` or ``projects``.
    Returns HTML fragment with config options.
    """
    account_id = request.GET.get('account')
    # Handle both single project and multi-project forms
    project_id = request.GET.get('project')
    projects = request.GET.get('projects')

    if project_id:
        project_ids = [project_id]
    elif projects:
        project_ids = [pid for pid in projects.split(',') if pid]
    else:
        project_ids = []

    current_value = request.GET.get('det_config_url', '')

    if not account_id or not project_ids:
        logger.error(
            'Missing required params for fetch_config_files: '
            'account_id=%s project_ids=%s',
            account_id,
            project_ids,
        )
        return render(
            request,
            'exports/partials/config_options.html',
            {
                'configs': [],
                'errors': ['Missing account_id or project_ids'],
                'is_multi_project': False,
                'current_value': current_value,
            },
        )

    account = get_object_or_404(CommCareAccount, id=account_id)
    projects = CommCareProject.objects.filter(id__in=project_ids)
    if not projects.exists():
        logger.error(
            'No valid projects found for fetch_config_files: '
            'account_id=%s project_ids=%s',
            account_id,
            project_ids,
        )
        return render(
            request,
            'exports/partials/config_options.html',
            {
                'configs': [],
                'errors': ['No valid projects found'],
                'is_multi_project': False,
                'current_value': current_value,
            },
        )

    all_configs = []
    errors = []
    for project in projects:
        try:
            configs = fetch_available_configs(
                server_url=project.server.url,
                domain=project.domain,
                username=account.username,
                api_key=account.api_key,
            )
            for config in configs:
                all_configs.append(
                    {
                        'domain': project.domain,
                        'name': config.get('name', 'Unnamed'),
                        'det_config_url': config.get('det_config_url'),
                    }
                )
        except Exception as err:
            logger.error(
                'Error fetching configs for %s: %s: %s',
                project.domain,
                type(err).__name__,
                err,
            )
            errors.append(f'Could not fetch configs for {project.domain}.')

    is_multi_project = len(projects) > 1

    return render(
        request,
        'exports/partials/config_options.html',
        {
            'configs': all_configs,
            'errors': errors,
            'is_multi_project': is_multi_project,
            'current_value': current_value,
        },
    )


@admin_required
def download_commcare_export_log(request):
    """
    Download the commcare_export.log file from the configured log directory.
    """
    log_file_path = os.path.join(settings.LOG_DIR, 'commcare_export.log')

    if not os.path.exists(log_file_path):
        raise Http404('Log file not found')

    with open(log_file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename=commcare_export.log'
        )
        return response
