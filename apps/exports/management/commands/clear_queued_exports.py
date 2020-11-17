from itertools import chain

from django.core.management.base import BaseCommand

from apps.exports.models import ExportRun, MultiProjectExportRun


class Command(BaseCommand):
    help = 'Clears all exports with status "queued".'

    def handle(self, **options):
        queued_runs = chain(
            ExportRun.objects.filter(status=ExportRun.QUEUED),
            MultiProjectExportRun.objects.filter(status=ExportRun.QUEUED)
        )
        for export_run in queued_runs:

            export_run.mark_skipped()
