from django.utils import timezone

from celery import shared_task

from apps.exports.templatetags.dateformat_tags import readable_timedelta
from .models import ExportConfig, MultiProjectExportConfig
from .runner import run_export, run_multi_project_export


@shared_task(bind=True)
def run_all_exports_task(self):
    for export in ExportConfig.objects.all():
        run_export(export)


@shared_task(bind=True)
def run_export_task(self, export_id):
    export = ExportConfig.objects.get(id=export_id)
    export_run = run_export(export)
    return {
        'run_time': export_run.created_at.isoformat(),
        'status': export_run.status,
        'duration': export_run.get_duration_display(),
        'log': export_run.log,
    }


@shared_task(bind=True)
def run_multi_project_export_task(self, export_id):
    run_start = timezone.now()
    export = MultiProjectExportConfig.objects.get(id=export_id)
    # todo: consolidate runs with more info
    export_run = run_multi_project_export(export)[-1]
    run_end = timezone.now()
    return {
        'run_time': export_run.created_at.isoformat(),
        'status': export_run.status,
        'duration': readable_timedelta(run_end - run_start),
        'log': export_run.log,
    }
