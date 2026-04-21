import logging

from celery import shared_task
from django.utils import timezone

from apps.web.templatetags.dateformat_tags import readable_timedelta

from .models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)
from .runner import run_export, run_multi_project_export

logger = logging.getLogger(__name__)


@shared_task
def run_scheduled_export_task(export_config_id):
    """Celery-beat entry point for a single ExportConfig."""
    try:
        export = ExportConfig.objects.get(id=export_config_id)
    except ExportConfig.DoesNotExist:
        logger.warning(
            'run_scheduled_export_task: ExportConfig %s no longer exists, '
            'skipping.',
            export_config_id,
        )
        return
    _enqueue_scheduled_export(export, ExportRun, run_export_task)


@shared_task
def run_scheduled_multi_export_task(export_config_id):
    """Celery-beat entry point for a single MultiProjectExportConfig."""
    try:
        export = MultiProjectExportConfig.objects.get(id=export_config_id)
    except MultiProjectExportConfig.DoesNotExist:
        logger.warning(
            'run_scheduled_multi_export_task: MultiProjectExportConfig %s no '
            'longer exists, skipping.',
            export_config_id,
        )
        return
    _enqueue_scheduled_export(
        export, MultiProjectExportRun, run_multi_project_export_task
    )


def _enqueue_scheduled_export(export_config, run_model, next_task):
    """
    Common entry-point logic for celery-beat scheduled export tasks.

    Skips enqueueing if a run is already queued, then creates a new run
    record and dispatches the worker task.
    """
    if export_config.has_queued_runs():
        return
    export_record = run_model.objects.create(
        base_export_config=export_config,
        export_config_version=export_config.latest_version,
        triggered_from_ui=False,
    )
    next_task.delay(export_record.id, force_sync_all_data=False)


@shared_task(bind=True)
def run_export_task(self, export_run_id, force_sync_all_data):
    export_run = ExportRun.objects.select_related('base_export_config').get(
        id=export_run_id
    )
    if export_run.status != ExportRun.Status.QUEUED:
        return
    export_run = run_export(export_run, force_sync_all_data)
    return {
        'run_time': export_run.created_at.isoformat(),
        'status': export_run.status,
        'duration': export_run.get_duration_display(),
        'log': export_run.log,
    }


@shared_task(bind=True)
def run_multi_project_export_task(self, export_run_id, force_sync_all_data):
    run_start = timezone.now()
    export_run = MultiProjectExportRun.objects.select_related(
        'base_export_config'
    ).get(id=export_run_id)
    export_runs = run_multi_project_export(export_run, force_sync_all_data)
    export_run = export_runs[-1] if export_runs else None
    if export_run:
        return {
            'run_time': export_run.created_at.isoformat(),
            'status': export_run.status,
            'duration': readable_timedelta(timezone.now() - run_start),
            'log': export_run.log,
        }
