from celery import shared_task

from .models import ExportConfig
from .runner import run_export


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
    }
