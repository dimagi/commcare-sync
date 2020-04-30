from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from .models import ExportConfig


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
    })

