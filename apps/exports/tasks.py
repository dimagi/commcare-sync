from celery import shared_task

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
    self.update_state(
        meta={
            'run_time': export_run.created_at,
            'status': export_run.status,
        }
    )
    return {
        'run_time': export_run.created_at.isoformat(),
        'status': export_run.status,
        'duration': export_run.get_duration_display(),
        'log': export_run.log,
    }


@shared_task(bind=True)
def run_multi_project_export_task(self, export_id):
    export = MultiProjectExportConfig.objects.get(id=export_id)
    export_run = run_multi_project_export(export)
    self.update_state(
        meta={
            'run_time': export_run.created_at,
            'status': export_run.status,
        }
    )
    return {
        'run_time': export_run.created_at.isoformat(),
        'status': export_run.status,
        'duration': export_run.get_duration_display(),
        'log': export_run.log,
    }
