from datetime import date, time

import pytest
import time_machine
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.schedules.models import Schedule


class ScheduleIntervalTestCase(TestCase):

    def test_create_interval_schedule_minutes(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=Schedule.IntervalUnit.MINUTES,
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.every == 30
        assert celery_schedule.period == 'minutes'

    def test_create_interval_schedule_hours(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=2,
            interval_unit=Schedule.IntervalUnit.HOURS,
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.every == 2
        assert celery_schedule.period == 'hours'

    def test_create_interval_schedule_days(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=7,
            interval_unit=Schedule.IntervalUnit.DAYS,
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.every == 7
        assert celery_schedule.period == 'days'

    def test_interval_schedule_str(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=15,
            interval_unit=Schedule.IntervalUnit.MINUTES,
        )

        assert str(schedule) == 'Every 15 minutes'


class ScheduleWeeklyTestCase(TestCase):

    def test_create_weekly_schedule(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            days_of_week=[1, 3, 5],  # Mon, Wed, Fri
            first_run_time=time(14, 30),
            timezone='America/New_York',
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.minute == '30'
        assert celery_schedule.hour == '14'
        assert celery_schedule.day_of_week == '1,3,5'
        assert celery_schedule.day_of_month == '*'
        assert celery_schedule.month_of_year == '*'
        assert celery_schedule.timezone.key == 'America/New_York'

    def test_weekly_schedule_str(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[0, 6],  # Sun, Sat
            first_run_time=time(9, 0),
        )

        assert str(schedule) == 'Weekly on Sun, Sat at 09:00:00'

    def test_weekly_schedule_unsorted_days(self):
        """Test that days are sorted in crontab schedule."""
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[5, 1, 3],  # Unsorted
            first_run_time=time(10, 0),
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.day_of_week == '1,3,5'  # Sorted


class ScheduleMonthlyTestCase(TestCase):
    """Test monthly schedules."""

    def test_create_monthly_schedule(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.MONTHLY,
            first_run_date=date(2025, 3, 15),
            first_run_time=time(8, 0),
            timezone='UTC',
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.minute == '0'
        assert celery_schedule.hour == '8'
        assert celery_schedule.day_of_month == '15'
        assert celery_schedule.day_of_week == '*'
        assert celery_schedule.month_of_year == '*'

    def test_monthly_schedule_str(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.MONTHLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(0, 0),
        )

        assert str(schedule) == 'Monthly on day 1 at 00:00:00'


class ScheduleQuarterlyTestCase(TestCase):

    def test_quarterly_starting_january(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 1, 10),
            first_run_time=time(12, 0),
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.day_of_month == '10'
        # Jan, Apr, Jul, Oct
        assert celery_schedule.month_of_year == '1,4,7,10'

    def test_quarterly_starting_february(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 2, 15),
            first_run_time=time(12, 0),
        )

        celery_schedule = schedule.create_celery_schedule()

        # Feb, May, Aug, Nov
        assert celery_schedule.month_of_year == '2,5,8,11'

    def test_quarterly_starting_march(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 3, 20),
            first_run_time=time(12, 0),
        )

        celery_schedule = schedule.create_celery_schedule()

        # Mar, Jun, Sep, Dec
        assert celery_schedule.month_of_year == '3,6,9,12'

    def test_quarterly_starting_november(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 11, 5),
            first_run_time=time(12, 0),
        )

        celery_schedule = schedule.create_celery_schedule()

        # Feb, May, Aug, Nov
        assert celery_schedule.month_of_year == '2,5,8,11'

    def test_quarterly_schedule_str(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 4, 1),
            first_run_time=time(15, 30),
        )

        assert str(schedule) == 'Quarterly on day 1 at 15:30:00'


class ScheduleSemiAnnuallyTestCase(TestCase):
    """Test semi-annual schedules."""

    def test_semi_annually_starting_january(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(9, 0),
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.month_of_year == '1,7'  # Jan, Jul

    def test_semi_annually_starting_march(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 3, 15),
            first_run_time=time(9, 0),
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.month_of_year == '3,9'  # Mar, Sep

    def test_semi_annually_starting_august(self):
        """Test semi-annual schedule starting in August (month wrapping)."""
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 8, 20),
            first_run_time=time(9, 0),
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.month_of_year == '2,8' # Feb, Aug

    def test_semi_annually_starting_october(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 10, 10),
            first_run_time=time(9, 0),
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.month_of_year == '4,10'  # Apr, Oct

    def test_semi_annually_schedule_str(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 6, 30),
            first_run_time=time(18, 0),
        )

        assert str(schedule) == 'Semi-annually on day 30 at 18:00:00'


class ScheduleAnnuallyTestCase(TestCase):
    """Test annual schedules."""

    def test_annually_schedule(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.ANNUALLY,
            first_run_date=date(2025, 12, 25),
            first_run_time=time(0, 0),
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.day_of_month == '25'
        assert celery_schedule.month_of_year == '12'

    def test_annually_different_month(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.ANNUALLY,
            first_run_date=date(2025, 3, 1),
            first_run_time=time(6, 30),
        )

        celery_schedule = schedule.create_celery_schedule()

        assert celery_schedule.day_of_month == '1'
        assert celery_schedule.month_of_year == '3'

    def test_annually_schedule_str(self):
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.ANNUALLY,
            first_run_date=date(2025, 7, 4),
            first_run_time=time(12, 0),
        )

        assert str(schedule) == 'Annually on day 4 at 12:00:00'


class ScheduleEdgeCasesTestCase(TestCase):
    """Test edge cases and special scenarios."""

    def test_schedule_ordering(self):
        with time_machine.travel('2025-01-01 10:00:00', tick=False):
            schedule1 = Schedule.objects.create(
                schedule_type=Schedule.ScheduleType.INTERVAL,
                interval_value=60,
                interval_unit=Schedule.IntervalUnit.MINUTES,
            )

        with time_machine.travel('2025-01-01 11:00:00', tick=False):
            schedule2 = Schedule.objects.create(
                schedule_type=Schedule.ScheduleType.INTERVAL,
                interval_value=30,
                interval_unit=Schedule.IntervalUnit.MINUTES,
            )

        schedules = list(Schedule.objects.all())
        assert schedules[0].id == schedule2.id
        assert schedules[1].id == schedule1.id

    def test_multiple_schedules_reuse_celery_schedules(self):
        schedule1 = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[1, 3, 5],
            first_run_time=time(14, 30),
        )

        schedule2 = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[1, 3, 5],
            first_run_time=time(14, 30),
        )

        celery_schedule1 = schedule1.create_celery_schedule()
        celery_schedule2 = schedule2.create_celery_schedule()

        # Should be the same object (get_or_create reuses existing)
        assert celery_schedule1.id == celery_schedule2.id


class ScheduleValidationTestCase(TestCase):
    """Test model validation for Schedule."""

    def test_interval_schedule_requires_interval_value(self):
        schedule = Schedule(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_unit=Schedule.IntervalUnit.MINUTES,
        )

        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()

        assert 'interval_value' in exc_info.value.message_dict

    def test_interval_schedule_requires_interval_unit(self):
        schedule = Schedule(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=30,
        )

        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()

        assert 'interval_unit' in exc_info.value.message_dict

    def test_monthly_schedule_requires_first_run_date(self):
        schedule = Schedule(
            schedule_type=Schedule.ScheduleType.MONTHLY,
            first_run_time=time(10, 0),
        )

        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()

        assert 'first_run_date' in exc_info.value.message_dict

    def test_quarterly_schedule_requires_first_run_date(self):
        schedule = Schedule(
            schedule_type=Schedule.ScheduleType.QUARTERLY,
            first_run_time=time(10, 0),
        )

        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()

        assert 'first_run_date' in exc_info.value.message_dict

    def test_semi_annually_schedule_requires_first_run_date(self):
        schedule = Schedule(
            schedule_type=Schedule.ScheduleType.SEMI_ANNUALLY,
            first_run_time=time(10, 0),
        )

        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()

        assert 'first_run_date' in exc_info.value.message_dict

    def test_annually_schedule_requires_first_run_date(self):
        schedule = Schedule(
            schedule_type=Schedule.ScheduleType.ANNUALLY,
            first_run_time=time(10, 0),
        )

        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()

        assert 'first_run_date' in exc_info.value.message_dict

    def test_weekly_schedule_requires_first_run_date(self):
        schedule = Schedule(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            days_of_week=[1, 3, 5],
            first_run_time=time(10, 0),
        )

        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()

        assert 'first_run_date' in exc_info.value.message_dict

    def test_weekly_schedule_requires_days_of_week(self):
        schedule = Schedule(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(10, 0),
            days_of_week=[],
        )

        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()

        assert 'days_of_week' in exc_info.value.message_dict

    def test_valid_interval_schedule_passes_validation(self):
        schedule = Schedule(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=Schedule.IntervalUnit.MINUTES,
        )

        schedule.full_clean()  # No ValidationError

    def test_valid_monthly_schedule_passes_validation(self):
        schedule = Schedule(
            schedule_type=Schedule.ScheduleType.MONTHLY,
            first_run_date=date(2025, 3, 15),
            first_run_time=time(10, 0),
        )

        schedule.full_clean()  # No ValidationError

    def test_valid_weekly_schedule_passes_validation(self):
        schedule = Schedule(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[1, 3, 5],
            first_run_time=time(10, 0),
        )

        schedule.full_clean()  # No ValidationError
