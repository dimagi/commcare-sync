from datetime import date, time, timedelta

import pytest
import time_machine
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from reversion.models import Version
from unmagic import fixture, use

from apps.db.models import Database
from apps.schedules.mixin import ScheduleMixin
from tests.fixtures import database

from ..models import (
    ForwardingConfig,
    ForwardingDestination,
    ForwardingRun,
)
from .fixtures import destination


@fixture
def config():
    yield ForwardingConfig.objects.create(
        name='Test Config',
        database=database(),
        destination=destination(),
        query='SELECT * FROM test',
    )


@fixture
def has_active_run_config():
    yield ForwardingConfig.objects.create(
        name='Test Config',
        database=database(),
        destination=destination(),
        query='SELECT 1',
    )


@use('db')
class TestForwardingConfig:

    @use(config)
    def test_str_method(self):
        assert str(config()) == 'Test Config'

    @use(config)
    def test_last_run_with_no_runs(self):
        assert config().last_run is None

    @use(config)
    def test_last_run_excludes_queued_runs(self):
        queued_run = ForwardingRun.objects.create(  # noqa: F841
            forwarding_config=config(),
            status=ForwardingRun.Status.QUEUED,
        )

        assert config().last_run is None

    @use(config)
    def test_last_run_returns_most_recent_non_queued(self):
        with time_machine.travel('2025-01-01 10:00:00', tick=False):
            run1 = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=config(),
                status=ForwardingRun.Status.COMPLETED,
            )

        with time_machine.travel('2025-01-01 11:00:00', tick=False):
            run2 = ForwardingRun.objects.create(
                forwarding_config=config(),
                status=ForwardingRun.Status.COMPLETED,
            )

        with time_machine.travel('2025-01-01 12:00:00', tick=False):
            queued_run = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=config(),
                status=ForwardingRun.Status.QUEUED,
            )

        assert config().last_run.id == run2.id

    @use(config)
    def test_has_queued_runs_with_no_runs(self):
        assert not config().has_queued_runs()

    @use(config)
    def test_has_queued_runs_returns_true_when_most_recent_is_queued(self):
        with time_machine.travel('2025-01-01 10:00:00', tick=False):
            completed_run = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=config(),
                status=ForwardingRun.Status.COMPLETED,
            )

        with time_machine.travel('2025-01-01 11:00:00', tick=False):
            queued_run = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=config(),
                status=ForwardingRun.Status.QUEUED,
            )

        assert config().has_queued_runs()

    @use(config)
    def test_has_queued_runs_returns_false_when_most_recent_is_not_queued(
        self,
    ):
        with time_machine.travel('2025-01-01 10:00:00', tick=False):
            queued_run = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=config(),
                status=ForwardingRun.Status.QUEUED,
            )

        with time_machine.travel('2025-01-01 11:00:00', tick=False):
            completed_run = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=config(),
                status=ForwardingRun.Status.COMPLETED,
            )

        assert not config().has_queued_runs()

    @use(config)
    def test_latest_version_returns_version(self):
        version = config().latest_version

        assert version is not None
        assert isinstance(version, Version)

    @use(config)
    def test_details_url(self):
        expected_url = f'/forwarding/{config().id}/'
        assert config().details_url == expected_url

    @use(config)
    def test_save_creates_revision(self):
        initial_version_count = Version.objects.get_for_object(
            config()
        ).count()

        config().query = 'SELECT * FROM updated_table'
        config().save()

        new_version_count = Version.objects.get_for_object(config()).count()
        assert new_version_count == initial_version_count + 1


@use('db')
class TestForwardingRun:

    @use(config)
    def test_str_method(self):
        with time_machine.travel('2025-01-15 14:30:00', tick=False):
            run = ForwardingRun.objects.create(
                forwarding_config=config(),
                status=ForwardingRun.Status.QUEUED,
            )

        assert str(run) == 'Test Config (2025-01-15 14:30:00+00:00)'

    @use(config)
    def test_duration_with_both_timestamps(self):
        run = ForwardingRun.objects.create(
            forwarding_config=config(),
            status=ForwardingRun.Status.COMPLETED,
            started_at=timezone.now(),
        )

        run.completed_at = run.started_at + timedelta(minutes=5, seconds=30)
        run.save()

        assert run.duration == timedelta(minutes=5, seconds=30)

    @use(config)
    def test_duration_with_missing_started_at(self):
        run = ForwardingRun.objects.create(
            forwarding_config=config(),
            status=ForwardingRun.Status.COMPLETED,
            completed_at=timezone.now(),
        )

        assert run.duration is None

    @use(config)
    def test_duration_with_missing_completed_at(self):
        run = ForwardingRun.objects.create(
            forwarding_config=config(),
            status=ForwardingRun.Status.STARTED,
            started_at=timezone.now(),
        )

        assert run.duration is None

    @use(config)
    def test_get_duration_display(self):
        with time_machine.travel('2025-01-15 10:00:00', tick=False):
            run = ForwardingRun.objects.create(
                forwarding_config=config(),
                status=ForwardingRun.Status.STARTED,
                started_at=timezone.now(),
            )

            run.completed_at = run.started_at + timedelta(hours=2, minutes=15)
            run.status = ForwardingRun.Status.COMPLETED
            run.save()

            duration_display = run.get_duration_display()

            assert duration_display == '2 hours 15 minutes'

    @use(config)
    def test_mark_skipped_success(self):
        run = ForwardingRun.objects.create(
            forwarding_config=config(),
            status=ForwardingRun.Status.QUEUED,
        )

        run.mark_skipped()

        run.refresh_from_db()
        assert run.status == ForwardingRun.Status.SKIPPED
        assert run.completed_at is not None

    @use(config)
    def test_mark_skipped_raises_exception_when_already_started(self):
        run = ForwardingRun.objects.create(
            forwarding_config=config(),
            status=ForwardingRun.Status.STARTED,
        )

        with pytest.raises(ValueError) as exc_info:
            run.mark_skipped()

        assert 'skipped' in str(exc_info.value)

    @use(config)
    def test_mark_skipped_raises_exception_when_already_completed(self):
        run = ForwardingRun.objects.create(
            forwarding_config=config(),
            status=ForwardingRun.Status.COMPLETED,
        )

        with pytest.raises(ValueError) as exc_info:
            run.mark_skipped()

        assert 'skipped' in str(exc_info.value)

    @use(config)
    def test_mark_skipped_raises_exception_when_already_failed(self):
        run = ForwardingRun.objects.create(
            forwarding_config=config(),
            status=ForwardingRun.Status.FAILED,
        )

        with pytest.raises(ValueError) as exc_info:
            run.mark_skipped()

        assert 'skipped' in str(exc_info.value)

    @use(config)
    def test_default_status_is_queued(self):
        run = ForwardingRun.objects.create(
            forwarding_config=config(),
        )

        assert run.status == ForwardingRun.Status.QUEUED


@use('db')
class TestDatabase:

    def test_str_method(self):
        db = Database.objects.create(
            name='Production DB',
            connection_string='postgresql://localhost/prod',
        )

        assert str(db) == 'Production DB'


@use('db')
class TestForwardingDestination:

    def test_str_method(self):
        dest = ForwardingDestination.objects.create(
            name='Example API',
            api_url='https://example.com/api',
        )

        assert str(dest) == 'Example API'

    def test_api_credentials_optional(self):
        dest = ForwardingDestination.objects.create(
            name='Public API',
            api_url='https://example.com/api',
        )

        assert dest.api_username == ''
        assert dest.api_password == ''

    def test_api_credentials_can_be_set(self):
        dest = ForwardingDestination.objects.create(
            name='Secured API',
            api_url='https://example.com/api',
            api_username='admin',
            api_password='secret',
        )

        assert dest.api_username == 'admin'
        assert dest.api_password == 'secret'


@use('db')
class TestForwardingScheduling:

    @use(database, destination)
    def test_creating_config_with_interval_schedule_creates_periodic_task(
        self,
    ):
        cfg = ForwardingConfig.objects.create(
            name='Scheduled Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )

        cfg.refresh_from_db()
        assert cfg.periodic_task is not None
        assert isinstance(cfg.periodic_task, PeriodicTask)
        assert cfg.periodic_task.enabled is True
        assert (
            cfg.periodic_task.task
            == 'apps.forwarding.tasks.run_scheduled_forwarding_task'
        )
        assert f'{cfg.id}' in cfg.periodic_task.args

    @use(database, destination)
    def test_creating_config_with_weekly_schedule_creates_periodic_task(self):
        cfg = ForwardingConfig.objects.create(
            name='Weekly Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(14, 30),
            days_of_week=[1, 3, 5],
        )

        cfg.refresh_from_db()
        assert cfg.periodic_task is not None
        assert isinstance(cfg.periodic_task, PeriodicTask)
        assert cfg.periodic_task.crontab is not None
        assert cfg.periodic_task.interval is None
        assert cfg.periodic_task.crontab.day_of_week == '1,3,5'

    @use(database, destination)
    def test_creating_config_without_schedule_does_not_create_periodic_task(
        self,
    ):
        cfg = ForwardingConfig.objects.create(
            name='Unscheduled Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
        )

        cfg.refresh_from_db()
        assert cfg.periodic_task is None

    @use(database, destination)
    def test_updating_config_schedule_updates_periodic_task(self):
        cfg = ForwardingConfig.objects.create(
            name='Config to Update',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        cfg.refresh_from_db()
        initial_task_id = cfg.periodic_task.id

        # Update the schedule
        cfg.interval_value = 60
        cfg.save()

        cfg.refresh_from_db()
        # The task should be updated (same ID)
        assert cfg.periodic_task.id == initial_task_id

    @use(database, destination)
    def test_deleting_config_deletes_periodic_task(self):
        cfg = ForwardingConfig.objects.create(
            name='Config to Delete',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        cfg.refresh_from_db()
        task_id = cfg.periodic_task.id

        cfg.delete()

        assert not PeriodicTask.objects.filter(id=task_id).exists()

    @use(database, destination)
    def test_removing_schedule_deletes_periodic_task(self):
        cfg = ForwardingConfig.objects.create(
            name='Config to Unschedule',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        cfg.refresh_from_db()
        task_id = cfg.periodic_task.id

        # Remove the schedule
        cfg.schedule_type = None
        cfg.save()

        cfg.refresh_from_db()
        assert cfg.periodic_task is None
        assert not PeriodicTask.objects.filter(id=task_id).exists()

    @use(database, destination)
    def test_is_paused_returns_true_when_no_schedule(self):
        cfg = ForwardingConfig.objects.create(
            name='Unscheduled Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
        )

        assert cfg.is_paused is True

    @use(database, destination)
    def test_is_paused_returns_true_when_no_periodic_task(self):
        cfg = ForwardingConfig.objects.create(
            name='No Task Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        cfg.refresh_from_db()
        # Delete the periodic task directly to simulate the condition
        cfg.periodic_task.delete()
        cfg.periodic_task = None

        assert cfg.is_paused is True

    @use(database, destination)
    def test_is_paused_returns_false_when_periodic_task_enabled(self):
        cfg = ForwardingConfig.objects.create(
            name='Enabled Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )

        cfg.refresh_from_db()
        assert cfg.is_paused is False

    @use(database, destination)
    def test_is_paused_returns_true_when_periodic_task_disabled(self):
        cfg = ForwardingConfig.objects.create(
            name='Disabled Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )

        cfg.refresh_from_db()
        cfg.periodic_task.enabled = False
        cfg.periodic_task.save()

        assert cfg.is_paused is True


@use('db')
class TestForwardingDestinationIsInUse:
    def test_not_in_use_when_no_configs(self):
        dest = ForwardingDestination.objects.create(
            name='IsInUse Destination',
            api_url='https://example.com/api/',
        )
        assert dest.is_in_use() is False

    def test_is_in_use_when_forwarding_config_exists(self):
        dest = ForwardingDestination.objects.create(
            name='IsInUse Destination',
            api_url='https://example.com/api/',
        )
        db = Database.objects.create(
            name='IsInUse DB',
            connection_string='postgresql://localhost/testdb',
        )
        ForwardingConfig.objects.create(
            name='IsInUse Config',
            database=db,
            destination=dest,
            query='SELECT 1',
        )
        assert dest.is_in_use() is True


@use('db')
class TestForwardingConfigHasActiveRun:

    @use(has_active_run_config)
    def test_false_with_no_runs(self):
        assert has_active_run_config().has_active_run is False

    @use(has_active_run_config)
    def test_false_when_run_is_completed(self):
        ForwardingRun.objects.create(
            forwarding_config=has_active_run_config(),
            status=ForwardingRun.Status.COMPLETED,
        )
        assert has_active_run_config().has_active_run is False

    @use(has_active_run_config)
    def test_false_when_run_is_failed(self):
        ForwardingRun.objects.create(
            forwarding_config=has_active_run_config(),
            status=ForwardingRun.Status.FAILED,
        )
        assert has_active_run_config().has_active_run is False

    @use(has_active_run_config)
    def test_true_when_run_is_queued(self):
        ForwardingRun.objects.create(
            forwarding_config=has_active_run_config(),
            status=ForwardingRun.Status.QUEUED,
        )
        assert has_active_run_config().has_active_run is True

    @use(has_active_run_config)
    def test_true_when_run_is_started(self):
        ForwardingRun.objects.create(
            forwarding_config=has_active_run_config(),
            status=ForwardingRun.Status.STARTED,
        )
        assert has_active_run_config().has_active_run is True

    @use(has_active_run_config)
    def test_uses_prefetched_runs_without_db_query(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        cfg = has_active_run_config()
        run = ForwardingRun.objects.create(
            forwarding_config=cfg,
            status=ForwardingRun.Status.QUEUED,
        )
        cfg._all_runs = [run]
        with CaptureQueriesContext(connection) as ctx:
            result = cfg.has_active_run
        assert len(ctx) == 0
        assert result is True
