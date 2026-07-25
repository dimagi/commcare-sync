import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from django_q.tasks import async_task

from apps.web.templatetags.dateformat_tags import readable_timedelta

from .models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)
from .runner import run_export, run_multi_project_export

logger = logging.getLogger(__name__)


def run_all_exports_task(user_id=None):
    """Manual "Run All" trigger: enqueue a run for every non-paused export."""
    user = None
    if user_id is not None:
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.warning(
                'run_all_exports_task: user %s no longer exists',
                user_id,
            )

    # ``is_paused`` is a derived property (depends on periodic_task state), not
    # a DB column, so the filter has to happen in Python.
    for export in ExportConfig.objects.select_related('periodic_task').all():
        if export.is_paused or export.has_active_run:
            continue
        _create_and_dispatch_export_run(
            export,
            ExportRun,
            run_export_task,
            triggered_from_ui=True,
            triggered_by=user,
        )

    for multi_export in (
        MultiProjectExportConfig
        .objects
        .select_related('periodic_task')
        .all()
    ):
        if multi_export.is_paused or multi_export.has_active_run:
            continue
        _create_and_dispatch_export_run(
            multi_export,
            MultiProjectExportRun,
            run_multi_project_export_task,
            triggered_from_ui=True,
            triggered_by=user,
        )


def run_scheduled_export_task(export_config_id):
    """Scheduler entry point for a single ExportConfig."""
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


def run_scheduled_multi_export_task(export_config_id):
    """Scheduler entry point for a single MultiProjectExportConfig."""
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


def _create_and_dispatch_export_run(
    export_config,
        run_model,
        next_task,
        *,
        triggered_from_ui=False,
        triggered_by=None,
):
    export_record = run_model.objects.create(
        base_export_config=export_config,
        export_config_version=export_config.latest_version,
        triggered_from_ui=triggered_from_ui,
        triggered_by=triggered_by,
    )
    async_task(next_task, export_record.id, start_over=False)


def _enqueue_scheduled_export(export_config, run_model, next_task):
    """Scheduler entry point: skip if already queued, then create and dispatch."""
    if export_config.has_queued_runs():
        return
    _create_and_dispatch_export_run(export_config, run_model, next_task)


def run_export_task(export_run_id, start_over):
    export_run = ExportRun.objects.select_related('base_export_config').get(
        id=export_run_id
    )
    if export_run.status != ExportRun.Status.QUEUED:
        return
    export_run = run_export(export_run, start_over)
    return {
        'run_time': export_run.created_at.isoformat(),
        'status': export_run.status,
        'duration': export_run.get_duration_display(),
        'log': export_run.log,
    }


def run_multi_project_export_task(export_run_id, start_over):
    run_start = timezone.now()
    export_run = MultiProjectExportRun.objects.select_related(
        'base_export_config'
    ).get(id=export_run_id)
    export_runs = run_multi_project_export(export_run, start_over)
    export_run = export_runs[-1] if export_runs else None
    if export_run:
        return {
            'run_time': export_run.created_at.isoformat(),
            'status': export_run.status,
            'duration': readable_timedelta(timezone.now() - run_start),
            'log': export_run.log,
        }
