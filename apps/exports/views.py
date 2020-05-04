from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ExportConfigForm
from .models import ExportConfig
from .tasks import run_export_task


@login_required
def home(request):
    exports = ExportConfig.objects.all()
    return render(request, 'exports/exports_home.html', {
        'active_tab': 'exports',
        'exports': exports,
    })


@login_required
def create_export_config(request):
    if request.method == 'POST':
        form = ExportConfigForm(request.POST, request.FILES)
        if form.is_valid():
            export = form.save()
            messages.success(request, f'Export {export.name} was successfully created.')
            return HttpResponseRedirect(reverse('exports:export_details', args=[export.id]))
    else:
        form = ExportConfigForm()

    return render(request, 'exports/create_export.html', {
        'active_tab': 'create_export',
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
        'active_tab': 'create_export',
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
@require_POST
def run_export(request, export_id):
    # just to validate the export exists so we can send feedback to the UI
    export = get_object_or_404(ExportConfig, id=export_id)
    result = run_export_task.delay(export_id)
    return HttpResponse(result.task_id)
