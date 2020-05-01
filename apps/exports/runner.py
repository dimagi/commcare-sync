import subprocess

from django.utils import timezone

from .models import ExportConfig, ExportRun


def run_export(export_config: ExportConfig):
    export_record = ExportRun.objects.create(export_config=export_config)
    command = [
        'commcare-export',
        '--project', export_config.project.domain,
        '--username', export_config.account.username,
        '--auth-mode', 'apikey',
        '--password', export_config.account.api_key,
        '--output-format', 'sql',
        '--output', export_config.database.connection_string,
        '--batch-size', '500',
        '--verbose',
        '--query', export_config.config_file.path,
    ]
    result = subprocess.run(command, capture_output=True)
    export_record.completed_at = timezone.now()
    export_record.status = _process_status_to_status_field(result.returncode)
    # commcare-export seems to use only stderr for logging
    export_record.log = result.stderr.decode('utf-8')
    export_record.save()
    return export_record


def _process_status_to_status_field(process_status):
    if process_status == 0:
        return ExportRun.COMPLETED
    else:
        return ExportRun.FAILED
