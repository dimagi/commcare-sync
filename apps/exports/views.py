from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

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
