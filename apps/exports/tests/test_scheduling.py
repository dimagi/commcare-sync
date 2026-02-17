from datetime import timedelta

from django.utils import timezone

from apps.exports.models import ExportRun
from apps.exports.tests.conftest import export_config_db_fixture


@export_config_db_fixture
def test_export_is_scheduled_to_run():
    export_config = export_config_db_fixture()

    # A config with no export runs should be scheduled
    assert export_config.is_scheduled_to_run()

    # A config that has an export_run in the QUEUED state should be seen as "scheduled"
    export_run = ExportRun.objects.create(
        base_export_config=export_config,
    )
    assert export_config.is_scheduled_to_run()

    # A completed export that is failed shouldn't be rescheduled
    export_run.status = ExportRun.FAILED
    export_run.completed_at = timezone.now() - timedelta(minutes=5)
    export_run.save()
    assert not export_config.is_scheduled_to_run()

    # Once time_between_runs delay has passed, the export should be scheduled to run again
    export_config.time_between_runs = 10
    export_run.completed_at = timezone.now() - timedelta(minutes=15)
    export_run.save()
    assert export_config.is_scheduled_to_run()

    export_run.delete()


@export_config_db_fixture
def test_should_spawn_task():
    export_config = export_config_db_fixture()

    export_run = ExportRun.objects.create(
        base_export_config=export_config,
    )

    assert not export_config.should_create_export_run()

    export_run.delete()
