from datetime import timedelta

import pytest
import time_machine
from django.utils import timezone
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

    def test_method_defaults_to_post(self):
        dest = ForwardingDestination.objects.create(
            name='Defaults API',
            api_url='https://example.com/api',
        )

        assert dest.http_method == ForwardingDestination.HttpMethod.POST
        assert dest.http_method == 'POST'

    def test_method_can_be_put(self):
        dest = ForwardingDestination.objects.create(
            name='PUT API',
            api_url='https://example.com/api',
            http_method=ForwardingDestination.HttpMethod.PUT,
        )

        assert dest.http_method == 'PUT'


@use('db')
class TestForwardingScheduling:

    @use(database, destination)
    def test_creating_config_with_schedule_sets_next_run(self):
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
        assert cfg.next_run_at is not None
        assert cfg.next_run_at > timezone.now()
        assert cfg.SCHEDULED_TASK == (
            'apps.forwarding.tasks.run_scheduled_forwarding_task'
        )

    @use(database, destination)
    def test_creating_config_without_schedule_has_no_next_run(self):
        cfg = ForwardingConfig.objects.create(
            name='Unscheduled Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
        )

        cfg.refresh_from_db()
        assert cfg.next_run_at is None

    @use(database, destination)
    def test_updating_schedule_recomputes_next_run(self):
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
        first = cfg.next_run_at

        cfg.interval_value = 60
        cfg.save()

        cfg.refresh_from_db()
        assert cfg.next_run_at > first

    @use(database, destination)
    def test_removing_schedule_clears_next_run(self):
        cfg = ForwardingConfig.objects.create(
            name='Config to Unschedule',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )

        cfg.schedule_type = None
        cfg.save()

        cfg.refresh_from_db()
        assert cfg.next_run_at is None

    @use(database, destination)
    def test_disabling_schedule_clears_next_run(self):
        cfg = ForwardingConfig.objects.create(
            name='Config to Disable',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )

        cfg.schedule_enabled = False
        cfg.save()

        cfg.refresh_from_db()
        assert cfg.next_run_at is None

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
    def test_is_paused_returns_false_when_schedule_enabled(self):
        cfg = ForwardingConfig.objects.create(
            name='Enabled Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )

        assert cfg.is_paused is False

    @use(database, destination)
    def test_is_paused_returns_true_when_schedule_disabled(self):
        cfg = ForwardingConfig.objects.create(
            name='Disabled Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
            schedule_enabled=False,
        )

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
