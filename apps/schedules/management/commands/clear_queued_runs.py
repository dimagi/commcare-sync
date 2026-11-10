from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import capfirst

from apps.commcare.models import RunBaseModel
from apps.schedules.tasks import RUN_MODELS


class Command(BaseCommand):
    help = (
        'Mark every queued run, of every run type, as skipped. This '
        'includes runs that are only waiting for a free worker; their '
        'tasks will then do nothing. Use it when a lost task has left a '
        'config blocked by a run that will never start.'
    )

    def handle(self, **options):
        total = 0
        now = timezone.now()
        for run_model in RUN_MODELS:
            # One conditional update, so a run that a worker claims in the
            # meantime is left STARTED.
            count = run_model.objects.filter(
                status=RunBaseModel.Status.QUEUED
            ).update(status=RunBaseModel.Status.SKIPPED, completed_at=now)
            if count:
                name = capfirst(run_model._meta.verbose_name_plural)
                self.stdout.write(f'{name}: {count} skipped')
            total += count
        if not total:
            self.stdout.write('No queued runs to skip')
