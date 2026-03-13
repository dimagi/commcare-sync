"""
Tests for ScheduleMixin functionality.

These tests exercise the schedule validation, celery schedule creation,
and schedule_display logic via ForwardingConfig as the concrete model.
"""
from datetime import date, time

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.exports.models import ExportDatabase
from apps.forwarding.models import ForwardingConfig, ForwardingDestination
from apps.schedules.mixin import ScheduleMixin

User = get_user_model()


class ScheduleMixinTestBase(TestCase):
    """Base class providing common test fixtures."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass'
        )
        self.database = ExportDatabase.objects.create(
            name='Test DB',
            connection_string='postgresql://localhost/test',
            owner=self.user,
        )
        self.destination = ForwardingDestination.objects.create(
            name='Test API',
            api_url='https://example.com/api',
            owner=self.user,
        )

    def _make_config(self, **schedule_kwargs):
        """Create a ForwardingConfig with schedule fields."""
        return ForwardingConfig.objects.create(
            name='Test Config',
            database=self.database,
            destination=self.destination,
            query='SELECT 1',
            created_by=self.user,
            **schedule_kwargs,
        )


class IntervalScheduleTestCase(ScheduleMixinTestBase):

    def test_create_interval_schedule_minutes(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.every == 30
        assert celery_schedule.period == 'minutes'

    def test_create_interval_schedule_hours(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=2,
            interval_unit=ScheduleMixin.IntervalUnit.HOURS,
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.every == 2
        assert celery_schedule.period == 'hours'

    def test_create_interval_schedule_days(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=7,
            interval_unit=ScheduleMixin.IntervalUnit.DAYS,
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.every == 7
        assert celery_schedule.period == 'days'

    def test_interval_schedule_display(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=15,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        assert config.schedule_display == 'Every 15 minutes'


class WeeklyScheduleTestCase(ScheduleMixinTestBase):

    def test_create_weekly_schedule(self):
        config = self._make_config(
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

    def test_weekly_schedule_display(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[0, 6],
            first_run_time=time(9, 0),
        )
        assert config.schedule_display == 'Weekly on Sun, Sat at 09:00:00'

    def test_weekly_schedule_unsorted_days(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[5, 1, 3],
            first_run_time=time(10, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.day_of_week == '1,3,5'


class MonthlyScheduleTestCase(ScheduleMixinTestBase):

    def test_create_monthly_schedule(self):
        config = self._make_config(
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

    def test_monthly_schedule_display(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.MONTHLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(0, 0),
        )
        assert config.schedule_display == 'Monthly on day 1 at 00:00:00'


class QuarterlyScheduleTestCase(ScheduleMixinTestBase):

    def test_quarterly_starting_january(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 1, 10),
            first_run_time=time(12, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.day_of_month == '10'
        assert celery_schedule.month_of_year == '1,4,7,10'

    def test_quarterly_starting_february(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 2, 15),
            first_run_time=time(12, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '2,5,8,11'

    def test_quarterly_starting_march(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 3, 20),
            first_run_time=time(12, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '3,6,9,12'

    def test_quarterly_starting_november(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 11, 5),
            first_run_time=time(12, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '2,5,8,11'

    def test_quarterly_schedule_display(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_date=date(2025, 4, 1),
            first_run_time=time(15, 30),
        )
        assert config.schedule_display == 'Quarterly on day 1 at 15:30:00'


class SemiAnnuallyScheduleTestCase(ScheduleMixinTestBase):

    def test_semi_annually_starting_january(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(9, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '1,7'

    def test_semi_annually_starting_march(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 3, 15),
            first_run_time=time(9, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '3,9'

    def test_semi_annually_starting_august(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 8, 20),
            first_run_time=time(9, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '2,8'

    def test_semi_annually_starting_october(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 10, 10),
            first_run_time=time(9, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.month_of_year == '4,10'

    def test_semi_annually_schedule_display(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_date=date(2025, 6, 30),
            first_run_time=time(18, 0),
        )
        assert config.schedule_display == 'Semi-annually on day 30 at 18:00:00'


class AnnuallyScheduleTestCase(ScheduleMixinTestBase):

    def test_annually_schedule(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.ANNUALLY,
            first_run_date=date(2025, 12, 25),
            first_run_time=time(0, 0),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.day_of_month == '25'
        assert celery_schedule.month_of_year == '12'

    def test_annually_different_month(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.ANNUALLY,
            first_run_date=date(2025, 3, 1),
            first_run_time=time(6, 30),
        )
        celery_schedule = config.create_celery_schedule()
        assert celery_schedule.day_of_month == '1'
        assert celery_schedule.month_of_year == '3'

    def test_annually_schedule_display(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.ANNUALLY,
            first_run_date=date(2025, 7, 4),
            first_run_time=time(12, 0),
        )
        assert config.schedule_display == 'Annually on day 4 at 12:00:00'


class ScheduleEdgeCasesTestCase(ScheduleMixinTestBase):

    def test_multiple_configs_reuse_celery_schedules(self):
        config1 = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[1, 3, 5],
            first_run_time=time(14, 30),
        )
        config2 = ForwardingConfig.objects.create(
            name='Test Config 2',
            database=self.database,
            destination=self.destination,
            query='SELECT 2',
            created_by=self.user,
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[1, 3, 5],
            first_run_time=time(14, 30),
        )
        celery_schedule1 = config1.create_celery_schedule()
        celery_schedule2 = config2.create_celery_schedule()
        assert celery_schedule1.id == celery_schedule2.id

    def test_has_schedule_false_when_no_schedule_type(self):
        config = self._make_config()
        assert config.has_schedule is False

    def test_has_schedule_true_when_schedule_type_set(self):
        config = self._make_config(
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        assert config.has_schedule is True

    def test_schedule_display_empty_when_no_schedule(self):
        config = self._make_config()
        assert config.schedule_display == ''


class ScheduleValidationTestCase(ScheduleMixinTestBase):

    def _make_unsaved_config(self, **schedule_kwargs):
        return ForwardingConfig(
            name='Test Config',
            database=self.database,
            destination=self.destination,
            query='SELECT 1',
            created_by=self.user,
            **schedule_kwargs,
        )

    def test_no_schedule_passes_validation(self):
        config = self._make_unsaved_config()
        config.full_clean()  # No ValidationError

    def test_interval_schedule_requires_interval_value(self):
        config = self._make_unsaved_config(
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'interval_value' in exc_info.value.message_dict

    def test_interval_schedule_requires_interval_unit(self):
        config = self._make_unsaved_config(
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'interval_unit' in exc_info.value.message_dict

    def test_monthly_schedule_requires_first_run_date(self):
        config = self._make_unsaved_config(
            schedule_type=ScheduleMixin.ScheduleType.MONTHLY,
            first_run_time=time(10, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'first_run_date' in exc_info.value.message_dict

    def test_quarterly_schedule_requires_first_run_date(self):
        config = self._make_unsaved_config(
            schedule_type=ScheduleMixin.ScheduleType.QUARTERLY,
            first_run_time=time(10, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'first_run_date' in exc_info.value.message_dict

    def test_semi_annually_schedule_requires_first_run_date(self):
        config = self._make_unsaved_config(
            schedule_type=ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
            first_run_time=time(10, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'first_run_date' in exc_info.value.message_dict

    def test_annually_schedule_requires_first_run_date(self):
        config = self._make_unsaved_config(
            schedule_type=ScheduleMixin.ScheduleType.ANNUALLY,
            first_run_time=time(10, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'first_run_date' in exc_info.value.message_dict

    def test_weekly_schedule_requires_first_run_date(self):
        config = self._make_unsaved_config(
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            days_of_week=[1, 3, 5],
            first_run_time=time(10, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'first_run_date' in exc_info.value.message_dict

    def test_weekly_schedule_requires_days_of_week(self):
        config = self._make_unsaved_config(
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(10, 0),
            days_of_week=[],
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'days_of_week' in exc_info.value.message_dict

    def test_valid_interval_schedule_passes_validation(self):
        config = self._make_unsaved_config(
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        config.full_clean()

    def test_valid_monthly_schedule_passes_validation(self):
        config = self._make_unsaved_config(
            schedule_type=ScheduleMixin.ScheduleType.MONTHLY,
            first_run_date=date(2025, 3, 15),
            first_run_time=time(10, 0),
        )
        config.full_clean()

    def test_valid_weekly_schedule_passes_validation(self):
        config = self._make_unsaved_config(
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            days_of_week=[1, 3, 5],
            first_run_time=time(10, 0),
        )
        config.full_clean()
