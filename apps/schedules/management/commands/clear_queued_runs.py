from itertools import chain

from django.core.management.base import BaseCommand

from apps.exports.models import ExportRun, MultiProjectExportRun
from apps.forwarding.models import ForwardingRun
from apps.refreshes.models import RefreshRun


class Command(BaseCommand):
    help = (
        'Clears stuck "queued" runs across all run types (exports, '
        'multi-project exports, forwarding, and refreshes). '
        '`has_active_run` treats a QUEUED run as active forever if its '
        'worker task never arrives, so this is the escape hatch for '
        'a config wedged that way.'
    )

    def handle(self, **options):
        queued_runs = chain(
            ExportRun.objects.filter(status=ExportRun.Status.QUEUED),
            MultiProjectExportRun.objects.filter(
                status=MultiProjectExportRun.Status.QUEUED
            ),
            ForwardingRun.objects.filter(status=ForwardingRun.Status.QUEUED),
            RefreshRun.objects.filter(status=RefreshRun.Status.QUEUED),
        )
        for run in queued_runs:
            run.mark_skipped()
