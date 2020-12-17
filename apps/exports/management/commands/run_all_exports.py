from django.core.management.base import BaseCommand

from apps.exports.models import ExportConfig, ExportRun
from apps.exports.runner import run_export
from reversion.models import Version


class Command(BaseCommand):
    help = 'Run all export configs in the database.'

    def handle(self, **options):
        for export_config in ExportConfig.objects.all():
            latest_export_config_version = Version.objects.get_for_object(export_config)[0]
            export_run = ExportRun.objects.create(base_export_config=export_config,
                                                  export_config_version=latest_export_config_version)
            run_export(export_run)
