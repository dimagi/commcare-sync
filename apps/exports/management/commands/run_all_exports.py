from django.core.management.base import BaseCommand

from apps.exports.tasks import run_all_exports_task


class Command(BaseCommand):
    help = 'Run all export configs in the database.'

    def handle(self, **options):
        run_all_exports_task()
