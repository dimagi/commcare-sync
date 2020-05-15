import subprocess

from django.conf import settings
from django.utils import timezone

from .models import ExportConfig, ExportRun, MultiProjectExportConfig, MultiProjectExportRun


def run_multi_project_export(multi_export_config: MultiProjectExportConfig):
    runs = []
    for project in multi_export_config.projects.all():
        export_record = MultiProjectExportRun.objects.create(export_config=multi_export_config, project=project)
        _run_export_for_project(multi_export_config, project, export_record)
        runs.append(export_record)
    return runs


def run_export(export_config: ExportConfig):
    export_record = ExportRun.objects.create(export_config=export_config)


def _run_export_for_project(export_config, project, export_record):
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
    try:
        result = subprocess.run(command, capture_output=True)
    except Exception as e:
        export_record.status = ExportRun.FAILED
        export_record.log = str(e)
    else:
        export_record.status = _process_status_to_status_field(result.returncode)
        # commcare-export seems to use only stderr for logging
        export_record.log = result.stderr.decode('utf-8')
    export_record.completed_at = timezone.now()
    export_record.save()
    return export_record


def _process_status_to_status_field(process_status):
    if process_status == 0:
        return ExportRun.COMPLETED
    else:
        return ExportRun.FAILED
