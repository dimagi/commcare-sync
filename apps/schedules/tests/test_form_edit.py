"""Tests for editing schedules via ScheduleForm."""

from datetime import date, time

import pytest

from apps.schedules.forms import ScheduleForm
from apps.schedules.models import Schedule


@pytest.mark.django_db
class TestScheduleFormEdit:
    """Test that ScheduleForm properly populates fields when editing."""

    def test_edit_weekly_schedule_populates_days_of_week(self):
        """Test that editing a weekly schedule properly selects the days checkboxes."""
        # Create a weekly schedule with specific days
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(10, 30),
            timezone='America/New_York',
            days_of_week=[1, 3, 5],  # Monday, Wednesday, Friday
        )

        # Create form with existing instance
        form = ScheduleForm(instance=schedule)

        # The form's initial data should include the days
        assert form.initial['days_of_week'] == [1, 3, 5]

    def test_edit_interval_schedule_has_empty_days_of_week(self):
        """Test that editing an interval schedule has empty days_of_week."""
        # Create an interval schedule
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=Schedule.IntervalUnit.MINUTES,
            days_of_week=[],  # Empty list
        )

        # Create form with existing instance
        form = ScheduleForm(instance=schedule)

        # The form's initial data should be empty list
        assert form.initial['days_of_week'] == []

    def test_submit_edited_weekly_schedule_with_changed_days(self):
        """Test that submitting an edit with changed days works correctly."""
        # Create a weekly schedule
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(10, 30),
            timezone='UTC',
            days_of_week=[1, 3, 5],  # Monday, Wednesday, Friday
        )

        # Submit form with different days
        form_data = {
            'schedule_type': Schedule.ScheduleType.WEEKLY,
            'first_run_date': '2025-01-01',
            'first_run_time': '10:30',
            'timezone': 'UTC',
            'days_of_week': [0, 6],  # Sunday, Saturday
        }
        form = ScheduleForm(form_data, instance=schedule)

        assert form.is_valid(), form.errors
        updated_schedule = form.save()

        # Verify the days were updated
        updated_schedule.refresh_from_db()
        assert updated_schedule.days_of_week == [0, 6]

    def test_edit_weekly_schedule_with_all_days(self):
        """Test editing a weekly schedule that runs all days."""
        # Create a weekly schedule with all days
        schedule = Schedule.objects.create(
            schedule_type=Schedule.ScheduleType.WEEKLY,
            first_run_date=date(2025, 1, 1),
            first_run_time=time(9, 0),
            timezone='UTC',
            days_of_week=[0, 1, 2, 3, 4, 5, 6],
        )

        # Create form with existing instance
        form = ScheduleForm(instance=schedule)

        # All checkboxes should be selected
        assert form.initial['days_of_week'] == [0, 1, 2, 3, 4, 5, 6]
