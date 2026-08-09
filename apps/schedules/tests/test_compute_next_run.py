from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

import pytest

from apps.exports.models import ExportConfig
from apps.schedules.mixin import ScheduleMixin

AFTER = datetime(2026, 7, 1, 10, 0, tzinfo=dt_timezone.utc)  # a Wednesday

INTERVAL_6H = {
    'schedule_type': ScheduleMixin.ScheduleType.INTERVAL,
    'interval_value': 6,
    'interval_unit': ScheduleMixin.IntervalUnit.HOURS,
}
WEEKLY = {
    'schedule_type': ScheduleMixin.ScheduleType.WEEKLY,
    'first_run_date': date(2026, 1, 1),
    'first_run_time': time(8, 0),
}


class TestComputeNextRun:

    @pytest.mark.parametrize(('schedule', 'after', 'expected'), [
        pytest.param({}, AFTER, None, id='no-schedule'),
        pytest.param(
            INTERVAL_6H, AFTER, AFTER + timedelta(hours=6),
            id='interval-adds-interval-to-after',
        ),
        pytest.param(
            {
                'schedule_type': ScheduleMixin.ScheduleType.INTERVAL,
                'interval_value': 45,
                'interval_unit': ScheduleMixin.IntervalUnit.MINUTES,
            },
            AFTER, AFTER + timedelta(minutes=45),
            # Pins IntervalUnit.MINUTES to timedelta's `minutes` kwarg.
            id='interval-minutes-uses-minutes-kwarg',
        ),
        pytest.param(
            {
                'schedule_type': ScheduleMixin.ScheduleType.INTERVAL,
                'interval_value': 3,
                'interval_unit': ScheduleMixin.IntervalUnit.DAYS,
            },
            AFTER, AFTER + timedelta(days=3),
            # Pins IntervalUnit.DAYS to timedelta's `days` kwarg (with no
            # first_run_date, so it exercises `after + interval` directly,
            # unlike interval-waits-for-future-first-run below).
            id='interval-days-uses-days-kwarg',
        ),
        pytest.param(
            {
                'schedule_type': ScheduleMixin.ScheduleType.INTERVAL,
                'interval_value': 1,
                'interval_unit': ScheduleMixin.IntervalUnit.DAYS,
                'first_run_date': date(2026, 8, 1),
                'first_run_time': time(9, 0),
            },
            AFTER,
            datetime(2026, 8, 1, 9, 0, tzinfo=dt_timezone.utc),
            id='interval-waits-for-future-first-run',
        ),
        pytest.param(
            {**WEEKLY, 'days_of_week': [0]},  # 0 = Sunday
            AFTER,
            datetime(2026, 7, 5, 8, 0, tzinfo=dt_timezone.utc),
            id='weekly-sunday-is-day-zero',
        ),
        pytest.param(
            {**WEEKLY, 'days_of_week': [3], 'first_run_time': time(23, 0)},
            AFTER,
            datetime(2026, 7, 1, 23, 0, tzinfo=dt_timezone.utc),
            id='weekly-same-day-later-time-runs-today',
        ),
        pytest.param(
            {
                **WEEKLY,
                'days_of_week': [0],
                'first_run_date': date(2026, 8, 2),  # a future Sunday
            },
            AFTER,
            datetime(2026, 8, 2, 8, 0, tzinfo=dt_timezone.utc),
            id='weekly-not-before-first-run-date',
        ),
        pytest.param(
            {
                **WEEKLY,
                'days_of_week': [1],  # Monday
                'first_run_time': time(9, 0),
                'timezone': 'America/New_York',
            },
            AFTER,
            # Monday 2026-07-06 09:00 EDT == 13:00 UTC.
            datetime(2026, 7, 6, 13, 0, tzinfo=dt_timezone.utc),
            id='schedule-timezone-is-honoured',
        ),
        pytest.param(
            {
                'schedule_type': ScheduleMixin.ScheduleType.MONTHLY,
                'first_run_date': date(2026, 1, 31),
                'first_run_time': time(0, 0),
            },
            datetime(2026, 1, 31, 1, 0, tzinfo=dt_timezone.utc),
            # February has no 31st; next run lands on 31 March.
            datetime(2026, 3, 31, 0, 0, tzinfo=dt_timezone.utc),
            id='monthly-day-31-skips-short-months',
        ),
        pytest.param(
            {
                'schedule_type': ScheduleMixin.ScheduleType.QUARTERLY,
                'first_run_date': date(2026, 2, 15),
                'first_run_time': time(6, 0),
            },
            datetime(2026, 3, 1, 0, 0, tzinfo=dt_timezone.utc),
            datetime(2026, 5, 15, 6, 0, tzinfo=dt_timezone.utc),
            id='quarterly-runs-every-third-month-from-anchor',
        ),
        pytest.param(
            {
                'schedule_type': ScheduleMixin.ScheduleType.QUARTERLY,
                'first_run_date': date(2026, 11, 5),
                'first_run_time': time(12, 0),
            },
            datetime(2026, 11, 5, 13, 0, tzinfo=dt_timezone.utc),
            # Next quarter after November crosses into the following year.
            datetime(2027, 2, 5, 12, 0, tzinfo=dt_timezone.utc),
            id='quarterly-crosses-year-boundary',
        ),
        pytest.param(
            {
                'schedule_type': ScheduleMixin.ScheduleType.SEMI_ANNUALLY,
                'first_run_date': date(2026, 2, 15),
                'first_run_time': time(6, 0),
            },
            datetime(2026, 3, 1, 0, 0, tzinfo=dt_timezone.utc),
            datetime(2026, 8, 15, 6, 0, tzinfo=dt_timezone.utc),
            id='semi-annually-runs-every-sixth-month',
        ),
        pytest.param(
            {
                'schedule_type': ScheduleMixin.ScheduleType.ANNUALLY,
                'first_run_date': date(2026, 2, 15),
                'first_run_time': time(6, 0),
            },
            datetime(2026, 3, 1, 0, 0, tzinfo=dt_timezone.utc),
            datetime(2027, 2, 15, 6, 0, tzinfo=dt_timezone.utc),
            id='annual-anniversary',
        ),
        pytest.param(
            # clean() requires first_run_date for calendar schedules, but
            # objects.create()/loaddata/shell edits can bypass validation.
            # _runs_on must degrade to False rather than raise AttributeError.
            {'schedule_type': ScheduleMixin.ScheduleType.MONTHLY},
            AFTER,
            None,
            id='calendar-schedule-without-first-run-date-returns-none',
        ),
    ])
    def test_compute_next_run(self, schedule, after, expected):
        # Unsaved instance: compute_next_run reads only schedule fields.
        cfg = ExportConfig(**schedule)
        assert cfg.compute_next_run(after) == expected


class TestComputeNextRunScanExhaustion:

    def test_logs_warning_and_returns_none_when_window_exhausted(self):
        # Anchored on 29 Feb, an ANNUALLY schedule only fires in leap
        # years. Queried just after a non-leap Feb, the next occurrence
        # (three years out) falls outside the two-year scan window, so
        # the schedule should be reported as diagnosably dead, not
        # silently unscheduled.
        cfg = ExportConfig(
            schedule_type=ScheduleMixin.ScheduleType.ANNUALLY,
            first_run_date=date(2024, 2, 29),
            first_run_time=time(0, 0),
        )
        after = datetime(2025, 3, 1, tzinfo=dt_timezone.utc)

        with patch('apps.schedules.mixin.logger') as mock_logger:
            result = cfg.compute_next_run(after)

        assert result is None
        mock_logger.warning.assert_called_once()
