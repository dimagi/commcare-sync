"""
Tests for ScheduleMixin functionality.

These tests exercise the schedule validation, celery schedule creation,
schedule_display, last_run, and has_active_run logic via ForwardingConfig
as the concrete model.
"""
from datetime import date, time

import pytest
from django.core.exceptions import ValidationError
from unmagic import use

from apps.forwarding.models import ForwardingConfig, ForwardingRun
from apps.schedules.mixin import ScheduleMixin
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
    def test_create_interval_schedule_minutes(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.every == 30
        assert celery_schedule.period == 'minutes'

    @use(database, destination)
    def test_create_interval_schedule_hours(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=2,
            interval_unit=ScheduleMixin.IntervalUnit.HOURS,
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.every == 2
        assert celery_schedule.period == 'hours'

    @use(database, destination)
    def test_create_interval_schedule_days(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=7,
            interval_unit=ScheduleMixin.IntervalUnit.DAYS,
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.every == 7
        assert celery_schedule.period == 'days'

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
    def test_create_weekly_schedule(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            days_of_week=[1, 3, 5],
            first_run_time=time(14, 30),
            timezone='America/New_York',
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.minute == '30'
        assert celery_schedule.hour == '14'
        assert celery_schedule.day_of_week == '1,3,5'
        assert celery_schedule.day_of_month == '*'
        assert celery_schedule.month_of_year == '*'
        assert celery_schedule.timezone.key == 'America/New_York'

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

    @use(database, destination)
    def test_weekly_schedule_unsorted_days(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[5, 1, 3],
            first_run_time=time(10, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.day_of_week == '1,3,5'


@use('db')
class TestMonthlySchedule:

    @use(database, destination)
    def test_create_monthly_schedule(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.MONTHLY,
            first_run_date=date(2025, 3, 15),
            first_run_time=time(8, 0),
            timezone='UTC',
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.minute == '0'
        assert celery_schedule.hour == '8'
        assert celery_schedule.day_of_month == '15'
        assert celery_schedule.day_of_week == '*'
        assert celery_schedule.month_of_year == '*'

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
    def test_quarterly_starting_january(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 1, 10),
            first_run_time=time(12, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.day_of_month == '10'
        assert celery_schedule.month_of_year == '1,4,7,10'

    @use(database, destination)
    def test_quarterly_starting_february(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 2, 15),
            first_run_time=time(12, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '2,5,8,11'

    @use(database, destination)
    def test_quarterly_starting_march(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 3, 20),
            first_run_time=time(12, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '3,6,9,12'

    @use(database, destination)
    def test_quarterly_starting_november(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 11, 5),
            first_run_time=time(12, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '2,5,8,11'

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
    def test_semi_annually_starting_january(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(9, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '1,7'

    @use(database, destination)
    def test_semi_annually_starting_march(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 3, 15),
            first_run_time=time(9, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '3,9'

    @use(database, destination)
    def test_semi_annually_starting_august(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 8, 20),
            first_run_time=time(9, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '2,8'

    @use(database, destination)
    def test_semi_annually_starting_october(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 10, 10),
            first_run_time=time(9, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '4,10'

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
    def test_annually_schedule(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.ANNUALLY,
            first_run_date=date(2025, 12, 25),
            first_run_time=time(0, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.day_of_month == '25'
        assert celery_schedule.month_of_year == '12'

    @use(database, destination)
    def test_annually_different_month(self):
        config = make_config(
            database(), destination(),
            schedule_type=ScheduleMixin.ScheduleType.ANNUALLY,
            first_run_date=date(2025, 3, 1),
            first_run_time=time(6, 30),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.day_of_month == '1'
        assert celery_schedule.month_of_year == '3'

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
    def test_multiple_configs_reuse_celery_schedules(self):
        db = database()
        dest = destination()
        config1 = make_config(
            db, dest,
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[1, 3, 5],
            first_run_time=time(14, 30),
        )
        config2 = ForwardingConfig.objects.create(
            name='Test Config 2',
            database=db,
            destination=dest,
            query='SELECT 2',
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[1, 3, 5],
            first_run_time=time(14, 30),
        )
        celery_schedule1 = config1.create_celery_schedule()
        celery_schedule2 = config2.create_celery_schedule()
        assert celery_schedule1.id == celery_schedule2.id

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

    def test_false_when_run_is_completed(self):
        config = make_config(database(), destination())
        ForwardingRun.objects.create(
            forwarding_config=config,
            status=ForwardingRun.Status.COMPLETED,
        )
        assert config.has_active_run is False

    def test_false_when_run_is_failed(self):
        config = make_config(database(), destination())
        ForwardingRun.objects.create(
            forwarding_config=config,
            status=ForwardingRun.Status.FAILED,
        )
        assert config.has_active_run is False

    def test_true_when_run_is_queued(self):
        config = make_config(database(), destination())
        ForwardingRun.objects.create(
            forwarding_config=config,
            status=ForwardingRun.Status.QUEUED,
        )
        assert config.has_active_run is True

    def test_true_when_run_is_started(self):
        config = make_config(database(), destination())
        ForwardingRun.objects.create(
            forwarding_config=config,
            status=ForwardingRun.Status.STARTED,
        )
        assert config.has_active_run is True

    def test_uses_prefetched_runs_without_db_query(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        config = make_config(database(), destination())
        run = ForwardingRun.objects.create(
            forwarding_config=config,
            status=ForwardingRun.Status.QUEUED,
        )
        config._all_runs = [run]
        with CaptureQueriesContext(connection) as ctx:
            result = config.has_active_run
        assert len(ctx) == 0
        assert result is True
