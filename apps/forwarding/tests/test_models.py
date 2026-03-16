from datetime import date, time, timedelta

import pytest
import time_machine
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from reversion.models import Version

from apps.db.models import Database
from apps.schedules.mixin import ScheduleMixin

from ..models import (
    ForwardingConfig,
    ForwardingDestination,
    ForwardingRun,
)

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestForwardingConfig:

    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass'
        )
        self.database = Database.objects.create(
            name='Test DB',
            connection_string='postgresql://localhost/test',
            owner=self.user,
        )
        self.destination = ForwardingDestination.objects.create(
            name='Test API',
            api_url='https://example.com/api',
            owner=self.user,
        )
        self.config = ForwardingConfig.objects.create(
            name='Test Config',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
        )

    def test_str_method(self):
        assert str(self.config) == 'Test Config'

    def test_last_run_with_no_runs(self):
        assert self.config.last_run is None

    def test_last_run_excludes_queued_runs(self):
        queued_run = ForwardingRun.objects.create(  # noqa: F841
            forwarding_config=self.config,
            status=ForwardingRun.Status.QUEUED,
        )

        assert self.config.last_run is None

    def test_last_run_returns_most_recent_non_queued(self):
        with time_machine.travel('2025-01-01 10:00:00', tick=False):
            run1 = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=self.config,
                status=ForwardingRun.Status.COMPLETED,
            )

        with time_machine.travel('2025-01-01 11:00:00', tick=False):
            run2 = ForwardingRun.objects.create(
                forwarding_config=self.config,
                status=ForwardingRun.Status.COMPLETED,
            )

        with time_machine.travel('2025-01-01 12:00:00', tick=False):
            queued_run = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=self.config,
                status=ForwardingRun.Status.QUEUED,
            )

        assert self.config.last_run.id == run2.id

    def test_has_queued_runs_with_no_runs(self):
        assert not self.config.has_queued_runs()

    def test_has_queued_runs_returns_true_when_most_recent_is_queued(self):
        with time_machine.travel('2025-01-01 10:00:00', tick=False):
            completed_run = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=self.config,
                status=ForwardingRun.Status.COMPLETED,
            )

        with time_machine.travel('2025-01-01 11:00:00', tick=False):
            queued_run = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=self.config,
                status=ForwardingRun.Status.QUEUED,
            )

        assert self.config.has_queued_runs()

    def test_has_queued_runs_returns_false_when_most_recent_is_not_queued(
        self,
    ):
        with time_machine.travel('2025-01-01 10:00:00', tick=False):
            queued_run = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=self.config,
                status=ForwardingRun.Status.QUEUED,
            )

        with time_machine.travel('2025-01-01 11:00:00', tick=False):
            completed_run = ForwardingRun.objects.create(  # noqa: F841
                forwarding_config=self.config,
                status=ForwardingRun.Status.COMPLETED,
            )

        assert not self.config.has_queued_runs()

    def test_latest_version_returns_version(self):
        version = self.config.latest_version

        assert version is not None
        assert isinstance(version, Version)

    def test_details_url(self):
        expected_url = f'/forwarding/{self.config.id}/'
        assert self.config.details_url == expected_url

    def test_save_creates_revision(self):
        initial_version_count = Version.objects.get_for_object(
            self.config
        ).count()

        self.config.query = 'SELECT * FROM updated_table'
        self.config.save()

        new_version_count = Version.objects.get_for_object(self.config).count()
        assert new_version_count == initial_version_count + 1


@pytest.mark.django_db
class TestForwardingRun:

    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass'
        )
        self.database = Database.objects.create(
            name='Test DB',
            connection_string='postgresql://localhost/test',
            owner=self.user,
        )
        self.destination = ForwardingDestination.objects.create(
            name='Test API',
            api_url='https://example.com/api',
            owner=self.user,
        )
        self.config = ForwardingConfig.objects.create(
            name='Test Config',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
        )

    def test_str_method(self):
        with time_machine.travel('2025-01-15 14:30:00', tick=False):
            run = ForwardingRun.objects.create(
                forwarding_config=self.config,
                status=ForwardingRun.Status.QUEUED,
            )

        assert str(run) == 'Test Config (2025-01-15 14:30:00+00:00)'

    def test_duration_with_both_timestamps(self):
        run = ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.COMPLETED,
            started_at=timezone.now(),
        )

        run.completed_at = run.started_at + timedelta(minutes=5, seconds=30)
        run.save()

        assert run.duration == timedelta(minutes=5, seconds=30)

    def test_duration_with_missing_started_at(self):
        run = ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.COMPLETED,
            completed_at=timezone.now(),
        )

        assert run.duration is None

    def test_duration_with_missing_completed_at(self):
        run = ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.STARTED,
            started_at=timezone.now(),
        )

        assert run.duration is None

    def test_get_duration_display(self):
        with time_machine.travel('2025-01-15 10:00:00', tick=False):
            run = ForwardingRun.objects.create(
                forwarding_config=self.config,
                status=ForwardingRun.Status.STARTED,
                started_at=timezone.now(),
            )

            run.completed_at = run.started_at + timedelta(hours=2, minutes=15)
            run.status = ForwardingRun.Status.COMPLETED
            run.save()

            duration_display = run.get_duration_display()

            assert duration_display == ' 2 hours 15 minutes'

    def test_mark_skipped_success(self):
        run = ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.QUEUED,
        )

        run.mark_skipped()

        run.refresh_from_db()
        assert run.status == ForwardingRun.Status.SKIPPED
        assert run.completed_at is not None

    def test_mark_skipped_raises_exception_when_already_started(self):
        run = ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.STARTED,
        )

        with pytest.raises(ValueError) as exc_info:
            run.mark_skipped()

        assert 'skipped' in str(exc_info.value)

    def test_mark_skipped_raises_exception_when_already_completed(self):
        run = ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.COMPLETED,
        )

        with pytest.raises(ValueError) as exc_info:
            run.mark_skipped()

        assert 'skipped' in str(exc_info.value)

    def test_mark_skipped_raises_exception_when_already_failed(self):
        run = ForwardingRun.objects.create(
            forwarding_config=self.config,
            status=ForwardingRun.Status.FAILED,
        )

        with pytest.raises(ValueError) as exc_info:
            run.mark_skipped()

        assert 'skipped' in str(exc_info.value)

    def test_default_status_is_queued(self):
        run = ForwardingRun.objects.create(
            forwarding_config=self.config,
        )

        assert run.status == ForwardingRun.Status.QUEUED


@pytest.mark.django_db
class TestDatabase:

    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass'
        )

    def test_str_method(self):
        database = Database.objects.create(
            name='Production DB',
            connection_string='postgresql://localhost/prod',
            owner=self.user,
        )

        assert str(database) == 'Production DB'


@pytest.mark.django_db
class TestForwardingDestination:

    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass'
        )

    def test_str_method(self):
        destination = ForwardingDestination.objects.create(
            name='Example API',
            api_url='https://example.com/api',
            owner=self.user,
        )

        assert str(destination) == 'Example API'

    def test_api_credentials_optional(self):
        destination = ForwardingDestination.objects.create(
            name='Public API',
            api_url='https://example.com/api',
            owner=self.user,
        )

        assert destination.api_username == ''
        assert destination.api_password == ''

    def test_api_credentials_can_be_set(self):
        destination = ForwardingDestination.objects.create(
            name='Secured API',
            api_url='https://example.com/api',
            api_username='admin',
            api_password='secret',
            owner=self.user,
        )

        assert destination.api_username == 'admin'
        assert destination.api_password == 'secret'


@pytest.mark.django_db(transaction=True)
class TestForwardingScheduling:

    def setup_method(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass'
        )
        self.database = Database.objects.create(
            name='Test DB',
            connection_string='postgresql://localhost/test',
            owner=self.user,
        )
        self.destination = ForwardingDestination.objects.create(
            name='Test API',
            api_url='https://example.com/api',
            owner=self.user,
        )

    def test_creating_config_with_interval_schedule_creates_periodic_task(
        self,
    ):
        config = ForwardingConfig.objects.create(
            name='Scheduled Config',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )

        config.refresh_from_db()
        assert config.periodic_task is not None
        assert isinstance(config.periodic_task, PeriodicTask)
        assert config.periodic_task.enabled is True
        assert (
            config.periodic_task.task
            == 'apps.forwarding.tasks.run_scheduled_forwarding_task'
        )
        assert f'{config.id}' in config.periodic_task.args

    def test_creating_config_with_weekly_schedule_creates_periodic_task(self):
        config = ForwardingConfig.objects.create(
            name='Weekly Config',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(14, 30),
            days_of_week=[1, 3, 5],
        )

        config.refresh_from_db()
        assert config.periodic_task is not None
        assert isinstance(config.periodic_task, PeriodicTask)
        assert config.periodic_task.crontab is not None
        assert config.periodic_task.interval is None
        assert config.periodic_task.crontab.day_of_week == '1,3,5'

    def test_creating_config_without_schedule_does_not_create_periodic_task(
        self,
    ):
        config = ForwardingConfig.objects.create(
            name='Unscheduled Config',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
        )

        config.refresh_from_db()
        assert config.periodic_task is None

    def test_updating_config_schedule_updates_periodic_task(self):
        config = ForwardingConfig.objects.create(
            name='Config to Update',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        config.refresh_from_db()
        initial_task_id = config.periodic_task.id

        # Update the schedule
        config.interval_value = 60
        config.save()

        config.refresh_from_db()
        # The task should be updated (same ID)
        assert config.periodic_task.id == initial_task_id

    def test_deleting_config_deletes_periodic_task(self):
        config = ForwardingConfig.objects.create(
            name='Config to Delete',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        config.refresh_from_db()
        task_id = config.periodic_task.id

        config.delete()

        assert not PeriodicTask.objects.filter(id=task_id).exists()

    def test_removing_schedule_deletes_periodic_task(self):
        config = ForwardingConfig.objects.create(
            name='Config to Unschedule',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        config.refresh_from_db()
        task_id = config.periodic_task.id

        # Remove the schedule
        config.schedule_type = None
        config.save()

        config.refresh_from_db()
        assert config.periodic_task is None
        assert not PeriodicTask.objects.filter(id=task_id).exists()

    def test_is_paused_returns_true_when_no_schedule(self):
        config = ForwardingConfig.objects.create(
            name='Unscheduled Config',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
        )

        assert config.is_paused is True

    def test_is_paused_returns_true_when_no_periodic_task(self):
        config = ForwardingConfig.objects.create(
            name='No Task Config',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        config.refresh_from_db()
        # Delete the periodic task directly to simulate the condition
        config.periodic_task.delete()
        config.periodic_task = None

        assert config.is_paused is True

    def test_is_paused_returns_false_when_periodic_task_enabled(self):
        config = ForwardingConfig.objects.create(
            name='Enabled Config',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )

        config.refresh_from_db()
        assert config.is_paused is False

    def test_is_paused_returns_true_when_periodic_task_disabled(self):
        config = ForwardingConfig.objects.create(
            name='Disabled Config',
            database=self.database,
            destination=self.destination,
            query='SELECT * FROM test',
            created_by=self.user,
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )

        config.refresh_from_db()
        config.periodic_task.enabled = False
        config.periodic_task.save()

        assert config.is_paused is True
