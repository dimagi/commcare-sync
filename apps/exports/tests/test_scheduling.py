from apps.exports.models import ExportRun
from apps.exports.tests.test_utils import BaseExportTestCase


class TestSchedule(BaseExportTestCase):
    def test_export_is_scheduled_to_run(self):

        self.assertTrue(self.export_config.is_scheduled_to_run())

        export_run = ExportRun.objects.create(
            base_export_config=self.export_config,
        )
        self.assertTrue(self.export_config.is_scheduled_to_run())

        export_run.status = ExportRun.FAILED
        export_run.save()
        self.assertFalse(self.export_config.is_scheduled_to_run())
