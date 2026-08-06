from unmagic import use

from apps.exports.models import ExportConfig, ExportRun
from apps.exports.tests.fixtures import export_config_db_fixture
from apps.schedules.mixin import ScheduleMixin


@use('db', export_config_db_fixture)
class TestExportScheduling:

    def test_interval_schedule_sets_next_run(self):
        """Saving a config with schedule fields set computes next_run_at via signals."""
        export_config = export_config_db_fixture()

        export_config.schedule_type = ScheduleMixin.ScheduleType.INTERVAL
        export_config.interval_value = 30
        export_config.interval_unit = ScheduleMixin.IntervalUnit.MINUTES
        export_config.save()

        export_config.refresh_from_db()
        assert export_config.next_run_at is not None
        assert export_config.is_paused is False

    def test_export_without_schedule_is_paused(self):
        """An export with no schedule_type should be considered paused."""
        export_config = export_config_db_fixture()

        assert export_config.schedule_type is None
        assert export_config.is_paused is True

    def test_has_queued_runs(self):
        """has_queued_runs() should detect runs in QUEUED status."""
        export_config = export_config_db_fixture()

        assert not export_config.has_queued_runs()

        run = ExportRun.objects.create(config=export_config)
        assert export_config.has_queued_runs()

        run.status = ExportRun.Status.COMPLETED
        run.save()
        assert not export_config.has_queued_runs()

        run.delete()

    def test_deleting_export_needs_no_schedule_cleanup(self):
        """Deletion no longer has external state to clean up; it simply succeeds."""
        export_config = export_config_db_fixture()

        export_config.schedule_type = ScheduleMixin.ScheduleType.INTERVAL
        export_config.interval_value = 60
        export_config.interval_unit = ScheduleMixin.IntervalUnit.MINUTES
        export_config.save()

        export_config.refresh_from_db()
        config_id = export_config.id
        export_config.delete()

        assert not ExportConfig.objects.filter(id=config_id).exists()
