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
            {
                'schedule_type': ScheduleMixin.ScheduleType.ANNUALLY,
                'first_run_date': date(2024, 2, 29),
                'first_run_time': time(0, 0),
            },
            datetime(2025, 3, 1, tzinfo=dt_timezone.utc),
            # Anchored on 29 February, an ANNUALLY schedule only fires in
            # leap years, so the next occurrence is four years out.
            datetime(2028, 2, 29, 0, 0, tzinfo=dt_timezone.utc),
            id='annual-on-29-february-skips-common-years',
        ),
        pytest.param(
            {
                'schedule_type': ScheduleMixin.ScheduleType.ANNUALLY,
                'first_run_date': date(2096, 2, 29),
                'first_run_time': time(0, 0),
            },
            datetime(2096, 2, 29, 0, 30, tzinfo=dt_timezone.utc),
            # The widest gap the Gregorian calendar allows: 2100 is
            # divisible by 100 but not 400, so it is not a leap year and
            # 2096 is followed by 2104. Starting on the anchor date with
            # first_run_time already past makes this the exact worst case
            # MAX_SCAN_DAYS is sized for.
            datetime(2104, 2, 29, 0, 0, tzinfo=dt_timezone.utc),
            id='annual-on-29-february-crosses-non-leap-century',
        ),
        pytest.param(
            {
                'schedule_type': ScheduleMixin.ScheduleType.MONTHLY,
                'first_run_date': date(2050, 1, 1),
                'first_run_time': time(8, 0),
            },
            AFTER,
            # A first_run_date beyond MAX_SCAN_DAYS must not be reported as
            # unscheduled: the scan starts at the anchor, not at `after`.
            datetime(2050, 1, 1, 8, 0, tzinfo=dt_timezone.utc),
            id='first-run-date-beyond-scan-window-still-scheduled',
        ),
        pytest.param(
            {
                'schedule_type': ScheduleMixin.ScheduleType.MONTHLY,
                'first_run_date': date(2016, 3, 15),
                'first_run_time': time(8, 0),
            },
            AFTER,
            # The converse: a long-past anchor must not drag the scan back
            # to it. The next run is the coming anniversary, not an old one.
            datetime(2026, 7, 15, 8, 0, tzinfo=dt_timezone.utc),
            id='first-run-date-long-past-scans-from-after',
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
        # clean() rejects a weekly schedule with no days selected, but
        # objects.create()/loaddata/shell edits can bypass validation. Such
        # a schedule never fires on any day, so the scan runs out. It
        # should be reported as diagnosably dead, not silently unscheduled.
        cfg = ExportConfig(
            schedule_type=ScheduleMixin.ScheduleType.WEEKLY,
            first_run_date=date(2026, 1, 1),
            first_run_time=time(8, 0),
            days_of_week=[],
        )

        with patch('apps.schedules.mixin.logger') as mock_logger:
            result = cfg.compute_next_run(AFTER)

        assert result is None
        mock_logger.warning.assert_called_once()
