from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ExportConfigForm, MultiProjectExportConfigForm
from .models import ExportConfig, MultiProjectExportConfig
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
            messages.success(request, f'Export {export.name} was successfully created.')
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
def export_details(request, export_id):
    export = get_object_or_404(ExportConfig, id=export_id)
    return render(request, 'exports/export_details.html', {
        'active_tab': 'exports',
        'export': export,
        'runs': export.runs.order_by('-created_at')[:25],
    })


@login_required
def multi_export_details(request, export_id):
    export = get_object_or_404(MultiProjectExportConfig, id=export_id)
    return render(request, 'exports/multi_project_export_details.html', {
        'active_tab': 'exports',
        'export': export,
        # 'runs': export.runs.order_by('-created_at')[:25],
    })


@login_required
@require_POST
def run_export(request, export_id):
    # just to validate the export exists so we can send feedback to the UI
    export = get_object_or_404(ExportConfig, id=export_id)
    result = run_export_task.delay(export_id)
    return HttpResponse(result.task_id)


@login_required
@require_POST
def run_multi_export(request, export_id):
    # just to validate the export exists so we can send feedback to the UI
    export = get_object_or_404(MultiProjectExportConfig, id=export_id)
    result = run_multi_project_export_task.delay(export_id)
    return HttpResponse(result.task_id)
