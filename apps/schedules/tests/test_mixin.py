"""
Tests for ScheduleMixin functionality.

These tests exercise the schedule validation, schedule_display, last_run,
and has_active_run logic via ForwardingConfig as the concrete model.
Periodicity computation (``compute_next_run``) is covered separately in
apps/schedules/tests/test_compute_next_run.py.
"""
from datetime import date, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from unmagic import use

from apps.forwarding.models import ForwardingConfig, ForwardingRun
from apps.schedules.mixin import OVERDUE_GRACE, ScheduleMixin
from tests.fixtures import database

from .fixtures import destination


def make_config(database_obj, destination_obj, **schedule_kwargs):
    """Create a ForwardingConfig with schedule fields."""
    return ForwardingConfig.objects.create(
        name='Test Config',
        database=database_obj,
        destination=destination_obj,
        query='SELECT 1',
        **schedule_kwargs,
    )


def make_unsaved_config(database_obj, destination_obj, **schedule_kwargs):
    return ForwardingConfig(
        name='Test Config',
        database=database_obj,
        destination=destination_obj,
        query='SELECT 1',
        **schedule_kwargs,
    )


@use('db')
class TestIntervalSchedule:

    @use(database, destination)
    def test_interval_schedule_display(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=15,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        assert config.schedule_display == 'Every 15 minutes'


@use('db')
class TestWeeklySchedule:

    @use(database, destination)
    def test_weekly_schedule_display(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[0, 6],
            first_run_time=time(9, 0),
        )
        assert config.schedule_display == 'Weekly on Sun, Sat at 09:00:00'


@use('db')
class TestMonthlySchedule:

    @use(database, destination)
    def test_monthly_schedule_display(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.MONTHLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(0, 0),
        )
        assert config.schedule_display == 'Monthly on day 1 at 00:00:00'


@use('db')
class TestQuarterlySchedule:

    @use(database, destination)
    def test_quarterly_schedule_display(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 4, 1),
            first_run_time=time(15, 30),
        )
        assert config.schedule_display == 'Quarterly on day 1 at 15:30:00'


@use('db')
class TestSemiAnnuallySchedule:

    @use(database, destination)
    def test_semi_annually_schedule_display(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 6, 30),
            first_run_time=time(18, 0),
        )
        assert config.schedule_display == 'Semi-annually on day 30 at 18:00:00'


@use('db')
class TestAnnuallySchedule:

    @use(database, destination)
    def test_annually_schedule_display(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.ANNUALLY,
            first_run_date=date(2025, 7, 4),
            first_run_time=time(12, 0),
        )
        assert config.schedule_display == 'Annually on day 4 at 12:00:00'


@use('db')
class TestScheduleEdgeCases:

    @use(database, destination)
    def test_has_schedule_false_when_no_schedule_type(self):
        config = make_config(database(), destination())
        assert config.has_schedule is False

    @use(database, destination)
    def test_has_schedule_true_when_schedule_type_set(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        assert config.has_schedule is True

    @use(database, destination)
    def test_schedule_display_empty_when_no_schedule(self):
        config = make_config(database(), destination())
        assert config.schedule_display == ''


@use('db')
class TestScheduleValidation:

    @use(database, destination)
    def test_no_schedule_passes_validation(self):
        config = make_unsaved_config(database(), destination())
        config.full_clean()  # No ValidationError

    @use(database, destination)
    def test_interval_schedule_requires_interval_value(self):
        config = make_unsaved_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'interval_value' in exc_info.value.message_dict

    @use(database, destination)
    def test_interval_schedule_requires_interval_unit(self):
        config = make_unsaved_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'interval_unit' in exc_info.value.message_dict

    @use(database, destination)
    def test_monthly_schedule_requires_first_run_date(self):
        config = make_unsaved_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.MONTHLY,
            first_run_time=time(10, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'first_run_date' in exc_info.value.message_dict

    @use(database, destination)
    def test_quarterly_schedule_requires_first_run_date(self):
        config = make_unsaved_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_time=time(10, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'first_run_date' in exc_info.value.message_dict

    @use(database, destination)
    def test_semi_annually_schedule_requires_first_run_date(self):
        config = make_unsaved_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_time=time(10, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'first_run_date' in exc_info.value.message_dict

    @use(database, destination)
    def test_annually_schedule_requires_first_run_date(self):
        config = make_unsaved_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.ANNUALLY,
            first_run_time=time(10, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'first_run_date' in exc_info.value.message_dict

    @use(database, destination)
    def test_weekly_schedule_requires_first_run_date(self):
        config = make_unsaved_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            days_of_week=[1, 3, 5],
            first_run_time=time(10, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'first_run_date' in exc_info.value.message_dict

    @use(database, destination)
    def test_weekly_schedule_requires_days_of_week(self):
        config = make_unsaved_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(10, 0),
            days_of_week=[],
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'days_of_week' in exc_info.value.message_dict

    @use(database, destination)
    def test_invalid_timezone_rejected(self):
        config = make_unsaved_config(
            database(), destination(),
            timezone='America/Newyork',
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'timezone' in exc_info.value.message_dict

    @use(database, destination)
    def test_valid_timezone_passes_validation(self):
        config = make_unsaved_config(
            database(), destination(),
            timezone='America/New_York',
        )
        config.full_clean()  # No ValidationError

    @use(database, destination)
    def test_valid_interval_schedule_passes_validation(self):
        config = make_unsaved_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        config.full_clean()

    @use(database, destination)
    def test_valid_monthly_schedule_passes_validation(self):
        config = make_unsaved_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.MONTHLY,
            first_run_date=date(2025, 3, 15),
            first_run_time=time(10, 0),
        )
        config.full_clean()

    @use(database, destination)
    def test_valid_weekly_schedule_passes_validation(self):
        config = make_unsaved_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[1, 3, 5],
            first_run_time=time(10, 0),
        )
        config.full_clean()


@use('db', database, destination)
class TestHasActiveRun:

    def test_false_with_no_runs(self):
        config = make_config(database(), destination())
        assert config.has_active_run is False

    @pytest.mark.parametrize('status,expected', [
        (ForwardingRun.Status.COMPLETED, False),
        (ForwardingRun.Status.FAILED, False),
        (ForwardingRun.Status.QUEUED, True),
        (ForwardingRun.Status.STARTED, True),
    ])
    def test_has_active_run_by_status(self, status, expected):
        config = make_config(database(), destination())
        ForwardingRun.objects.create(
            config=config,
            status=status,
        )
        assert config.has_active_run is expected

    def test_uses_prefetched_runs_without_db_query(self):
        config = make_config(database(), destination())
        run = ForwardingRun.objects.create(
            config=config,
            status=ForwardingRun.Status.QUEUED,
        )
        config._all_runs = [run]
        with CaptureQueriesContext(connection) as ctx:
            result = config.has_active_run_cached
        assert len(ctx) == 0
        assert result is True

    def test_has_active_run_ignores_a_stale_prefetch(self):
        config = make_config(database(), destination())
        ForwardingRun.objects.create(
            config=config, status=ForwardingRun.Status.STARTED
        )
        # A prefetch captured before the run existed must not be trusted
        # by the dispatch guard.
        config._all_runs = []

        assert config.has_active_run is True

    def test_has_active_run_cached_uses_the_prefetch(self):
        config = make_config(database(), destination())
        ForwardingRun.objects.create(
            config=config, status=ForwardingRun.Status.STARTED
        )
        config._all_runs = []

        assert config.has_active_run_cached is False

    def test_has_active_run_cached_falls_back_without_a_prefetch(self):
        config = make_config(database(), destination())
        ForwardingRun.objects.create(
            config=config, status=ForwardingRun.Status.STARTED
        )

        assert config.has_active_run_cached is True


@use('db', database, destination)
class TestIsOverdue:

    def make_config_due(self, due_at):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        # Assign directly: save() would have the post_save handler in
        # apps/schedules/signals.py recompute next_run_at.
        config.next_run_at = due_at
        return config

    def test_not_overdue_when_unscheduled(self):
        config = self.make_config_due(None)
        assert config.is_overdue is False

    def test_not_overdue_when_due_in_the_future(self):
        config = self.make_config_due(timezone.now() + timedelta(minutes=30))
        assert config.is_overdue is False

    def test_not_overdue_within_the_grace_period(self):
        # A dispatcher that runs once a minute is routinely a little late.
        config = self.make_config_due(timezone.now() - timedelta(minutes=1))
        assert config.is_overdue is False

    def test_overdue_past_the_grace_period(self):
        config = self.make_config_due(
            timezone.now() - OVERDUE_GRACE - timedelta(minutes=1)
        )
        assert config.is_overdue is True
