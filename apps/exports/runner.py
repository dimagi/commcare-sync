import subprocess

from django.conf import settings
from django.utils import timezone

from apps.exports.scheduling import export_is_scheduled_to_run
from .models import ExportRun, MultiProjectPartialExportRun, MultiProjectExportRun


def run_multi_project_export(multi_export_run: MultiProjectExportRun, force_sync_all_data=False,
                             ignore_schedule_checks=False):
    multi_export_config = multi_export_run.export_config
    multi_export_run.status = MultiProjectExportRun.STARTED
    multi_export_run.started_at = timezone.now()
    multi_export_run.save()
    runs = []
    for project in multi_export_config.projects.all():
        if ignore_schedule_checks or (
                export_is_scheduled_to_run(multi_export_config,
                                           multi_export_config.get_last_run_for_project(project))):
            export_record = MultiProjectPartialExportRun.objects.create(
                parent_run=multi_export_run,
                project=project,
                triggered_from_ui=multi_export_run.triggered_from_ui,
            )
            export_record = _run_export_for_project(multi_export_config, project, export_record, force_sync_all_data)
            runs.append(export_record)

    run_statuses = set([run.status for run in runs])
    if len(run_statuses) == 1:
        multi_export_run.status = run_statuses[0]
    else:
        multi_export_run.status = MultiProjectExportRun.MULTIPLE
    multi_export_run.completed_at = timezone.now()
    multi_export_run.save()
    return runs


def run_export(export_run: ExportRun, force=False):
    export_config = export_run.export_config
    return _run_export_for_project(export_config, export_config.project, export_run, force)


def _run_export_for_project(export_config, project, export_record, force):
    command = [
        settings.COMMCARE_EXPORT,
        '--project', project.domain,
        '--username', export_config.account.username,
        '--auth-mode', 'apikey',
        '--password', export_config.account.api_key,
        '--output-format', 'sql',
        '--output', export_config.database.connection_string,
        '--batch-size', '500',
        '--verbose',
        '--query', export_config.config_file.path,
    ]
    if force:
        command.append('--start-over')

    if export_config.extra_args:
        command.append(export_config.extra_args)

    export_record.status = ExportRun.STARTED
    export_record.started_at = timezone.now()
    export_record.save()
    try:
        # pipe both stdout and stderr to the same place https://stackoverflow.com/a/41172862/8207
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
    except Exception as e:
        export_record.status = ExportRun.FAILED
        export_record.log = str(e)
    else:
        export_record.status = _process_status_to_status_field(result.returncode)
        export_record.log = result.stdout
    export_record.completed_at = timezone.now()
    export_record.save()
    return export_record


def _process_status_to_status_field(process_status):
    if process_status == 0:
        return ExportRun.COMPLETED
    else:
        return ExportRun.FAILED
