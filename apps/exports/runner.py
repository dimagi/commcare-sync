import subprocess

from .models import ExportConfig


def run_export(export_config: ExportConfig):

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
