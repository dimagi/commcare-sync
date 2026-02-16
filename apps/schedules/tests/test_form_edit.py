"""Tests for editing schedule fields via ScheduleFormMixin."""

from datetime import date, time

import pytest

from apps.forwarding.forms import ForwardingConfigForm
from apps.forwarding.models import ForwardingConfig
from apps.schedules.mixin import ScheduleMixin


@pytest.mark.django_db(transaction=True)
class TestScheduleFormMixinEdit:
    def test_edit_weekly_schedule_populates_days_of_week(
        self, user, database, destination
    ):
        config = ForwardingConfig.objects.create(
            name='Weekly Config',
            database=database,
            destination=destination,
            query='SELECT 1',
            created_by=user,
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(10, 30),
            timezone='America/New_York',
            days_of_week=[1, 3, 5],
        )

        form = ForwardingConfigForm(instance=config)

        assert form.initial['days_of_week'] == [1, 3, 5]

    def test_edit_interval_schedule_has_empty_days_of_week(
        self, user, database, destination
    ):
        config = ForwardingConfig.objects.create(
            name='Interval Config',
            database=database,
            destination=destination,
            query='SELECT 1',
            created_by=user,
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
            days_of_week=[],
        )

        form = ForwardingConfigForm(instance=config)

        assert form.initial['days_of_week'] == []

    def test_submit_edited_weekly_schedule_with_changed_days(
        self, user, database, destination
    ):
        config = ForwardingConfig.objects.create(
            name='Weekly Config',
            database=database,
            destination=destination,
            query='SELECT 1',
            created_by=user,
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(10, 30),
            timezone='UTC',
            days_of_week=[1, 3, 5],
        )

        config.refresh_from_db()

        form_data = {
            'name': 'Weekly Config',
            'database': database.id,
            'destination': destination.id,
            'query': 'SELECT 1',
            'schedule_type': ScheduleMixin.ScheduleType.WEEKLY,
            'first_run_date': '2025-01-01',
            'first_run_time': '10:30',
            'timezone': 'UTC',
            'days_of_week': [0, 6],
        }
        form = ForwardingConfigForm(form_data, instance=config)

        assert form.is_valid(), form.errors
        updated_config = form.save()

        updated_config.refresh_from_db()
        assert updated_config.days_of_week == [0, 6]

    def test_edit_weekly_schedule_with_all_days(
        self, user, database, destination
    ):
        config = ForwardingConfig.objects.create(
            name='All Days Config',
            database=database,
            destination=destination,
            query='SELECT 1',
            created_by=user,
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(9, 0),
            timezone='UTC',
            days_of_week=[0, 1, 2, 3, 4, 5, 6],
        )

        form = ForwardingConfigForm(instance=config)

        assert form.initial['days_of_week'] == [0, 1, 2, 3, 4, 5, 6]
