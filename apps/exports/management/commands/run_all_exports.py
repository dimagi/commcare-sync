from django.core.management.base import BaseCommand

from apps.exports.tasks import run_all_exports_task


class Command(BaseCommand):
    help = (
        'Queue a run for every non-paused export config, then return '
        'immediately. A running Django-Q2 cluster is required to actually '
        'execute the queued runs.'
    )

    def handle(self, **options):
        run_all_exports_task()
