from django.utils import timezone

from celery import shared_task

from apps.exports.templatetags.dateformat_tags import readable_timedelta
from .models import ExportConfig, MultiProjectExportConfig, ExportRun, MultiProjectExportRun
from .runner import run_export, run_multi_project_export


@shared_task(bind=True)
def run_all_exports_task(self):
    for export in ExportConfig.objects.filter(is_paused=False):
        if export.is_scheduled_to_run() and not export.has_queued_runs():
            export_record = ExportRun.objects.create(base_export_config=export,
                                                     export_config_version=export.latest_version,
                                                     triggered_from_ui=False)
            run_export_task.delay(export_record.id, force_sync_all_data=False)
    for multi_export in MultiProjectExportConfig.objects.filter(is_paused=False):
        if multi_export.is_scheduled_to_run() and not multi_export.has_queued_runs():
            multi_export_record = MultiProjectExportRun.objects.create(base_export_config=multi_export,
                                                                       export_config_version=export.latest_version,
                                                                       triggered_from_ui=False)
            run_multi_project_export_task.delay(multi_export_record.id, force_sync_all_data=False)


@shared_task(bind=True)
def run_export_task(self, export_run_id, force_sync_all_data, ignore_schedule_checks=False):
    export_run = ExportRun.objects.select_related('base_export_config').get(id=export_run_id)
    export = export_run.base_export_config
    if export_run.status != ExportRun.QUEUED:
        # this export has already been run, ignore
        return
    if ignore_schedule_checks or export.is_scheduled_to_run():
        export_run = run_export(export_run, force_sync_all_data)
        return {
            'run_time': export_run.created_at.isoformat(),
            'status': export_run.status,
            'duration': export_run.get_duration_display(),
            'log': export_run.log,
        }
    else:
        export_run.mark_skipped()


@shared_task(bind=True)
def run_multi_project_export_task(self, export_run_id, force_sync_all_data, ignore_schedule_checks=False):
    run_start = timezone.now()
    export_run = MultiProjectExportRun.objects.select_related('base_export_config').get(id=export_run_id)
    # todo: consolidate runs with more info
    export_runs = run_multi_project_export(export_run, force_sync_all_data, ignore_schedule_checks)
    export_run = export_runs[-1] if export_runs else None
    if export_run:
        return {
            'run_time': export_run.created_at.isoformat(),
            'status': export_run.status,
            'duration': readable_timedelta(timezone.now() - run_start),
            'log': export_run.log,
        }
