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
    subprocess.run(command)
    export_record.completed_at = timezone.now()
    export_record.status = 'completed'
    export_record.save()
    return export_record
