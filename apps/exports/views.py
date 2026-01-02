import json
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from reversion.models import Version

from apps.commcare.models import CommCareAccount, CommCareProject
from commcare_sync.views import get_hide_skipped_from_request, get_ui_page_size

from .api_client import fetch_available_configs
from .forms import (
    CreateExportDatabaseForm,
    EditExportDatabaseForm,
    ExportConfigForm,
    MultiProjectExportConfigForm,
)
from .models import (
    ExportConfig,
    ExportDatabase,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)
from .tasks import run_export_task, run_multi_project_export_task


@login_required
def home(request):
    exports = ExportConfig.objects.order_by('-updated_at')
    multi_project_exports = MultiProjectExportConfig.objects.order_by('-updated_at')

    return render(request, 'exports/exports_home.html', {
        'active_tab': 'exports',
        'exports': exports,
        'multi_project_exports': multi_project_exports,
    })


@login_required
def create_export_config(request):

    if request.method == 'POST':
        form = ExportConfigForm(request.POST, request.FILES)
        if form.is_valid():
            export = form.save(commit=False)
            export.created_by = request.user
            export.save()
            messages.success(request, f'Export "{export.name}" was successfully created.')
            return HttpResponseRedirect(reverse('exports:export_details', args=[export.id]))
    else:
        form = ExportConfigForm()

    return render(request, 'exports/create_export.html', {
        'active_tab': 'create_export',
        'form': form,
    })


@login_required
def create_multi_export_config(request):
    if request.method == 'POST':
        form = MultiProjectExportConfigForm(request.POST, request.FILES)
        if form.is_valid():
            export = form.save(commit=False)
            export.created_by = request.user
            export.save()
            form.save_m2m()
            messages.success(request, f'Export {export.name} was successfully created.')
            return HttpResponseRedirect(reverse('exports:multi_export_details', args=[export.id]))
    else:
        form = MultiProjectExportConfigForm()

    return render(request, 'exports/create_multi_project_export.html', {
        'active_tab': 'create_multi_export',
        'form': form,
    })


@login_required
def edit_export_config(request, export_id):
    export = get_object_or_404(ExportConfig, id=export_id)
    if request.method == 'POST':
        form = ExportConfigForm(request.POST, request.FILES, instance=export)
        if form.is_valid():
            export = form.save()
            messages.success(request, f'Export {export.name} was successfully saved.')
            return HttpResponseRedirect(reverse('exports:export_details', args=[export.id]))
    else:
        form = ExportConfigForm(instance=export)

    return render(request, 'exports/edit_export.html', {
        'active_tab': 'exports',
        'form': form,
        'export': export,
    })


@login_required
def edit_multi_export_config(request, export_id):
    export = get_object_or_404(MultiProjectExportConfig, id=export_id)
    if request.method == 'POST':
        form = MultiProjectExportConfigForm(request.POST, request.FILES, instance=export)
        if form.is_valid():
            export = form.save()
            messages.success(request, f'Export {export.name} was successfully created.')
            return HttpResponseRedirect(reverse('exports:multi_export_details', args=[export.id]))
    else:
        form = MultiProjectExportConfigForm(instance=export)

    return render(request, 'exports/edit_multi_project_export.html', {
        'active_tab': 'create_multi_export',
        'form': form,
    })


@login_required
def delete_export_config(request, export_id):
    export = get_object_or_404(ExportConfig, id=export_id)
    if request.method == 'POST':
        export.delete()
        messages.success(request, f'Export file "{export.name}" was successfully deleted.')
        return HttpResponseRedirect(reverse('exports:home'))
    return render(request, 'exports/delete_export.html', {
        'active_tab': 'exports',
        'export': export,
    })


@login_required
def delete_multi_export_config(request, export_id):
    export = get_object_or_404(MultiProjectExportConfig, id=export_id)
    if request.method == 'POST':
        export.delete()
        messages.success(request, f'Export file "{export.name}" was successfully deleted.')
        return HttpResponseRedirect(reverse('exports:home'))
    return render(request, 'exports/delete_export.html', {
        'active_tab': 'exports',
        'export': export,
    })


@login_required
def export_details(request, export_id):
    export = get_object_or_404(ExportConfig, id=export_id)
    runs = export.runs
    hide_skipped = get_hide_skipped_from_request(request)
    if hide_skipped:
        runs = runs.exclude(status__in=[ExportRun.SKIPPED, ExportRun.QUEUED])

    return render(request, 'exports/export_details.html', {
        'active_tab': 'exports',
        'export': export,
        'runs': runs.order_by('-created_at')[:get_ui_page_size(request)],
        'hide_skipped': hide_skipped,
    })


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
    response = HttpResponse(export_file_field.read(), content_type='application/force-download')
    response['Content-Disposition'] = f'attachment; filename={os.path.basename(export_file_field.name)}'
    return response


@login_required
def multi_export_details(request, export_id):
    export = get_object_or_404(MultiProjectExportConfig, id=export_id)
    runs = export.runs
    hide_skipped = get_hide_skipped_from_request(request)
    if hide_skipped:
        runs = runs.exclude(status__in=[ExportRun.SKIPPED, ExportRun.QUEUED])

    return render(request, 'exports/multi_project_export_details.html', {
        'active_tab': 'exports',
        'export': export,
        'runs': runs.order_by('-created_at')[:get_ui_page_size(request)],
        'hide_skipped': hide_skipped,

    })


@login_required
def multi_export_run_details(request, export_id, run_id):
    export_run = get_object_or_404(MultiProjectExportRun, id=run_id)
    if export_run.base_export_config.id != export_id:
        raise Http404(f'Export id {export_id} did not match run value of {export_run.base_export_config.id }!')
    return render(request, 'exports/multi_project_export_run_details.html', {
        'active_tab': 'exports',
        'export_run': export_run,
        'export': export_run.base_export_config,
        'runs': export_run.partial_runs.order_by('-created_at')[:get_ui_page_size(request)],
    })


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
        triggering_user=request.user,
    )

    result = run_export_task.delay(export_record.id, force_sync_all_data=force_sync, ignore_schedule_checks=True)
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
        triggering_user=request.user
    )

    result = run_multi_project_export_task.delay(
        export_record.id, force_sync_all_data=force_sync, ignore_schedule_checks=True,
    )
    return HttpResponse(result.task_id)


@login_required
def databases(request):
    databases = ExportDatabase.objects.order_by('name')
    return render(request, 'exports/databases.html', {
        'active_tab': 'databases',
        'databases': databases,
    })


@user_passes_test(lambda u: u.is_superuser, login_url='/admin-required')  # type: ignore[union-attr]
def create_database(request):
    if request.method == 'POST':
        form = CreateExportDatabaseForm(request.POST, request.FILES)
        if form.is_valid():
            db = form.save(commit=False)
            db.owner = request.user
            db.save()
            messages.success(request, f'Database {db.name} was successfully created.')
            return HttpResponseRedirect(reverse('exports:databases'))
    else:
        form = CreateExportDatabaseForm()

    return render(request, 'exports/create_database.html', {
        'active_tab': 'create_export',
        'form': form,
    })


@user_passes_test(lambda u: u.is_superuser)  # type: ignore[union-attr]
def edit_database(request, database_id):
    db = get_object_or_404(ExportDatabase, id=database_id)
    if request.method == 'POST':
        form = EditExportDatabaseForm(request.POST, instance=db)
        if form.is_valid():
            db = form.save()
            messages.success(request, f'Database "{db.name}" was successfully updated.')
            return HttpResponseRedirect(reverse('exports:databases'))
    else:
        form = EditExportDatabaseForm(instance=db)

    return render(request, 'exports/edit_database.html', {
        'active_tab': 'create_export',
        'form': form,
    })


@login_required
def fetch_config_files(request):
    """
    AJAX endpoint to fetch available config files from CommCare HQ.

    Expects GET parameters: ``account_id`` and comma-separated ``project_ids``.
    """
    account_id = request.GET.get('account_id')
    project_ids = request.GET.get('project_ids', '').split(',')
    project_ids = [pid for pid in project_ids if pid]

    if not account_id or not project_ids:
        return JsonResponse(
            {'error': 'Missing account_id or project_ids'},
            status=400,
        )

    account = get_object_or_404(CommCareAccount, id=account_id)
    projects = CommCareProject.objects.filter(id__in=project_ids)
    if not projects.exists():
        return JsonResponse({'error': 'No valid projects found'}, status=400)

    all_configs = []
    errors = []
    for project in projects:
        try:
            configs = fetch_available_configs(
                server_url=project.server.url,
                domain=project.domain,
                username=account.username,
                api_key=account.api_key
            )
            for config in configs:
                all_configs.append({
                    'domain': project.domain,
                    'name': config.get('name', 'Unnamed'),
                    'det_config_url': config.get('det_config_url'),
                })
        except Exception as err:
            errors.append(f"{type(err).__name__}: {err}")

    data = {'configs': all_configs}
    if errors:
        data['errors'] = errors
    return JsonResponse(data)
