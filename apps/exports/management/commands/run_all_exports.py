from django.core.management.base import BaseCommand

from apps.exports.models import ExportConfig, ExportRun
from apps.exports.runner import run_export


class Command(BaseCommand):
    help = 'Run all export configs in the database.'

    def handle(self, **options):
        for export_config in ExportConfig.objects.all():
            export_run = ExportRun.objects.create(export_config=export_config)
            run_export(export_run)
