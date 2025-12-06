from datetime import timedelta

from apps.exports.models import ExportRun
from apps.exports.tests.test_utils import BaseExportTestCase
from django.utils import timezone


class TestSchedule(BaseExportTestCase):
    def test_export_is_scheduled_to_run(self):

        # A config with no export runs should be scheduled
        assert self.export_config.is_scheduled_to_run()

        # A config that has an export_run in the QUEUED state should be seen as "scheduled"
        export_run = ExportRun.objects.create(
            base_export_config=self.export_config,
        )
        self.addCleanup(export_run.delete)
        assert self.export_config.is_scheduled_to_run()

        # A completed export that is failed shouldn't be rescheduled
        export_run.status = ExportRun.FAILED
        export_run.completed_at = timezone.now() - timedelta(minutes=5)
        export_run.save()
        assert not self.export_config.is_scheduled_to_run()

        # Once time_between_runs delay has passed, the export should be scheduled to run again
        self.export_config.time_between_runs = 10
        export_run.completed_at = timezone.now() - timedelta(minutes=15)
        export_run.save()
        assert self.export_config.is_scheduled_to_run()

    def test_should_spawn_task(self):
        ExportRun.objects.create(
            base_export_config=self.export_config,
        )

        assert not self.export_config.should_create_export_run()
