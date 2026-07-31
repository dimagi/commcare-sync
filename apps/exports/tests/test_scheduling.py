from django_celery_beat.models import PeriodicTask
from unmagic import use

from apps.exports.models import ExportRun
from apps.exports.tests.fixtures import export_config_db_fixture
from apps.schedules.mixin import ScheduleMixin


@use('db', export_config_db_fixture)
class TestExportScheduling:

    def test_export_with_interval_schedule_creates_periodic_task(self):
        """When schedule fields are set and saved, a PeriodicTask should be created via signals."""
        export_config = export_config_db_fixture()

        export_config.schedule_type = ScheduleMixin.ScheduleType.INTERVAL
        export_config.interval_value = 30
        export_config.interval_unit = ScheduleMixin.IntervalUnit.MINUTES
        export_config.save()

        export_config.refresh_from_db()
        assert export_config.periodic_task is not None
        assert export_config.periodic_task.enabled is True
        assert not export_config.is_paused

    def test_export_without_schedule_is_paused(self):
        """An export with no schedule_type should be considered paused."""
        export_config = export_config_db_fixture()

        assert export_config.schedule_type is None
        assert export_config.is_paused is True

    def test_has_queued_runs(self):
        """has_queued_runs() should detect runs in QUEUED status."""
        export_config = export_config_db_fixture()

        assert not export_config.has_queued_runs()

        run = ExportRun.objects.create(base_export_config=export_config)
        assert export_config.has_queued_runs()

        run.status = ExportRun.Status.COMPLETED
        run.save()
        assert not export_config.has_queued_runs()

        run.delete()

    def test_deleting_export_cleans_up_periodic_task(self):
        """When an export with a PeriodicTask is deleted, the PeriodicTask should be cleaned up."""
        export_config = export_config_db_fixture()

        export_config.schedule_type = ScheduleMixin.ScheduleType.INTERVAL
        export_config.interval_value = 60
        export_config.interval_unit = ScheduleMixin.IntervalUnit.MINUTES
        export_config.save()

        export_config.refresh_from_db()
        periodic_task_id = export_config.periodic_task.id
        export_config.delete()

        assert not PeriodicTask.objects.filter(id=periodic_task_id).exists()
