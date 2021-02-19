import subprocess
from datetime import datetime, timedelta

from apps.exports.scheduling import export_is_scheduled_to_run
from django.conf import settings
from django.utils import timezone

from .models import (
    ExportRun,
    MultiProjectExportRun,
    MultiProjectPartialExportRun,
)

LOG_STREAM_DELAY = 30  # write the log every 30 seconds


def run_multi_project_export(multi_export_run: MultiProjectExportRun, force_sync_all_data=False,
                             ignore_schedule_checks=False):
    multi_export_config = multi_export_run.base_export_config
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
            export_record = _run_export_for_project(
                multi_export_config, project, export_record, force_sync_all_data
            )
            runs.append(export_record)

    run_statuses = set([run.status for run in runs])
    if len(run_statuses) == 1:
        multi_export_run.status = list(run_statuses)[0]
    else:
        multi_export_run.status = MultiProjectExportRun.MULTIPLE
    multi_export_run.completed_at = timezone.now()
    multi_export_run.save()
    return runs


def run_export(export_run: ExportRun, force=False):
    export_config = export_run.base_export_config
    return _run_export_for_project(export_config, export_config.project, export_run, force)


def _run_export_for_project(export_config, project, export_record, force):
    export_record.status = ExportRun.STARTED
    export_record.started_at = timezone.now()
    export_record.save()
    try:
        # pipe both stdout and stderr to the same place https://stackoverflow.com/a/41172862/8207
        process = subprocess.Popen(
            _compile_export_command(export_config, project, force),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        log_buffer = _stream_log(process, export_record)
        result = process.poll()
    except Exception as e:
        export_record.status = ExportRun.FAILED
        export_record.log = str(e)
    else:
        export_record.status = _process_status_to_status_field(result)
        export_record.log = "\n".join(log_buffer)
    export_record.completed_at = timezone.now()
    export_record.save()
    return export_record


def _stream_log(process, export_record):
    log_buffer = []
    start_time = datetime.utcnow()
    while True:
        output = process.stdout.readline()
        if process.poll() is not None and output == '':
            break
        if output:
            log_buffer.append(output.strip())
        if datetime.utcnow() - start_time >= timedelta(seconds=LOG_STREAM_DELAY):
            export_record.log = "{}\n\n{}".format(
                "\n".join(log_buffer),
                "Job still running, refresh the page to see more…"
            )
            export_record.save()
    return log_buffer


def _compile_export_command(export_config, project, force):
    command = [
        settings.COMMCARE_EXPORT,
        '--project', project.domain,
        '--username', export_config.account.username,
        '--auth-mode', 'apikey',
        '--password', export_config.account.api_key,
        '--output-format', 'sql',
        '--output', export_config.database.connection_string,
        '--batch-size', str(export_config.batch_size),
        '--verbose',
        '--query', export_config.config_file.path,
        '--commcare-hq', project.server.url.rstrip('/'),
    ]
    if force:
        command.append('--start-over')

    for extra_arg in export_config.extra_args.split(" "):
        if extra_arg:
            command.append(extra_arg)

    return command


def _process_status_to_status_field(process_status):
    if process_status == 0:
        return ExportRun.COMPLETED
    else:
        return ExportRun.FAILED
