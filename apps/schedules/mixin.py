import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.commcare.models import RunBaseModel

type AwareDatetime = datetime

logger = logging.getLogger(__name__)


def _validate_days_of_week(value):
    if not isinstance(value, list):
        raise ValidationError(_('days_of_week must be a list.'))
    for day in value:
        if not isinstance(day, int) or not (0 <= day <= 6):
            raise ValidationError(
                _('Invalid day of week: %(day)s. Must be an integer 0–6.'),
                params={'day': day},
            )


class ScheduleMixin(models.Model):
    """
    Abstract model mixin that adds scheduling fields to any config model.

    Concrete models must define:
        SCHEDULED_TASK: str - dotted path to the task run on schedule
        PERIODIC_TASK_PREFIX: str - prefix for the PeriodicTask name
        runs: reverse relation manager (e.g. from a ForeignKey on a Run model)
    """

    class ScheduleType(models.TextChoices):
        INTERVAL = 'interval', _('Every N minutes/hours/days')
        WEEKLY = 'weekly', _('Weekly on specific days')
        MONTHLY = 'monthly', _('Monthly on specific day')
        QUARTERLY = 'quarterly', _('Quarterly')
        SEMI_ANNUALLY = 'semi-annually', _('Semi-annually (twice per year)')
        ANNUALLY = 'annually', _('Annually')

    class IntervalUnit(models.TextChoices):
        MINUTES = 'minutes', _('Minutes')
        HOURS = 'hours', _('Hours')
        DAYS = 'days', _('Days')

    SCHEDULED_TASK: str
    PERIODIC_TASK_PREFIX: str

    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices,
        null=True,
        blank=True,
    )
    first_run_date = models.DateField(
        null=True, blank=True, help_text=_("Don't run before this date")
    )
    first_run_time = models.TimeField(
        default=time(0, 0), help_text=_('Time of day for first/recurring runs')
    )
    timezone = models.CharField(
        max_length=63,
        default='UTC',
        help_text=_(
            "Timezone for scheduled runs (e.g., 'America/New_York', 'UTC')"
        ),
    )
    interval_value = models.PositiveIntegerField(
        null=True, blank=True, help_text=_('Number of time units between runs')
    )
    interval_unit = models.CharField(
        max_length=10,
        choices=IntervalUnit.choices,
        null=True,
        blank=True,
        help_text=_('Time unit for interval'),
    )
    days_of_week = models.JSONField(
        default=list,
        blank=True,
        help_text=_(
            'List of day numbers: 0=Sunday, 1=Monday, ..., 6=Saturday'
        ),
        validators=[_validate_days_of_week],
    )
    periodic_task = models.OneToOneField(
        'django_celery_beat.PeriodicTask',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        abstract = True

    @property
    def has_schedule(self):
        return bool(self.schedule_type)

    @property
    def is_paused(self):
        """
        Returns True if scheduling is paused.

        A config is considered paused if:
        - It has no schedule, or
        - The schedule has no periodic_task, or
        - The periodic_task is disabled
        """
        if not self.has_schedule or not self.periodic_task:
            return True
        return not self.periodic_task.enabled

    def has_queued_runs(self):
        last_run = self.runs.order_by('-created_at').first()
        if last_run:
            return last_run.status == RunBaseModel.Status.QUEUED
        return False

    @property
    def last_run(self):
        all_runs = getattr(self, '_all_runs', None)
        if all_runs is not None:
            # Use prefetched data: filter out QUEUED in Python
            non_queued = [
                r for r in all_runs if r.status != RunBaseModel.Status.QUEUED
            ]
            return non_queued[0] if non_queued else None
        return (
            self.runs.exclude(status=RunBaseModel.Status.QUEUED)
            .order_by('-created_at')
            .first()
        )

    @property
    def has_active_run(self):
        active = {RunBaseModel.Status.QUEUED, RunBaseModel.Status.STARTED}
        all_runs = getattr(self, '_all_runs', None)
        if all_runs is not None:
            return any(r.status in active for r in all_runs)
        return self.runs.filter(status__in=active).exists()

    @property
    def schedule_display(self):
        if not self.schedule_type:
            return ''
        if self.schedule_type == self.ScheduleType.INTERVAL:
            return f'Every {self.interval_value} {self.interval_unit.lower()}'
        if self.schedule_type == self.ScheduleType.WEEKLY:
            day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
            days = ', '.join(day_names[d] for d in sorted(self.days_of_week))
            return f'Weekly on {days} at {self.first_run_time}'
        day = self.first_run_date.day if self.first_run_date else '?'
        if self.schedule_type == self.ScheduleType.MONTHLY:
            return f'Monthly on day {day} at {self.first_run_time}'
        if self.schedule_type == self.ScheduleType.QUARTERLY:
            return f'Quarterly on day {day} at {self.first_run_time}'
        if self.schedule_type == self.ScheduleType.SEMI_ANNUALLY:
            return f'Semi-annually on day {day} at {self.first_run_time}'
        if self.schedule_type == self.ScheduleType.ANNUALLY:
            return f'Annually on day {day} at {self.first_run_time}'
        return f'Schedule ({self.schedule_type})'

    def clean(self):
        """Validate that required fields are set based on schedule_type."""
        super().clean()

        if not self.schedule_type:
            return

        if self.schedule_type == self.ScheduleType.INTERVAL:
            if not self.interval_value:
                raise ValidationError(
                    {
                        'interval_value': _(
                            'Interval value is required for interval schedules.'
                        )
                    }
                )
            if not self.interval_unit:
                raise ValidationError(
                    {
                        'interval_unit': _(
                            'Interval unit is required for interval schedules.'
                        )
                    }
                )
        else:
            if not self.first_run_date:
                raise ValidationError(
                    {
                        'first_run_date': _(
                            'First run date is required for {schedule_type} '
                            'schedules.'
                        ).format(
                            schedule_type=self.get_schedule_type_display()
                        )
                    }
                )

            if self.schedule_type == self.ScheduleType.WEEKLY:
                if not self.days_of_week:
                    raise ValidationError(
                        {
                            'days_of_week': _(
                                'At least one day of the week must be '
                                'selected for weekly schedules.'
                            )
                        }
                    )

    def compute_next_run(self, after: AwareDatetime) -> AwareDatetime | None:
        """
        Return the next scheduled run as a timezome-aware datetime
        strictly after ``after`` (also an aware datetime), or None if
        there is no schedule.

        Calendar schedules follow cron semantics: a monthly schedule
        anchored on day 31 skips months without a 31st.

        .. note:: a ``first_run_time`` that falls in a DST gap or the
           repeated DST-fallback hour in a non-UTC ``timezone`` resolves
           to whatever timezone ``zoneinfo`` picks -- this is not
           specially handled.
        """
        if not self.has_schedule:
            return None
        tz = ZoneInfo(self.timezone)

        if self.schedule_type == self.ScheduleType.INTERVAL:
            interval = timedelta(**{self.interval_unit: self.interval_value})  # type: ignore
            if self.first_run_date:
                first = datetime.combine(
                    self.first_run_date, self.first_run_time, tzinfo=tz
                )
                if first > after:
                    return first
            return after + interval

        # Calendar-based schedules: scan forward day by day (bounded to
        # two years, enough for ANNUALLY plus skipped short months).
        candidate_date = after.astimezone(tz).date()
        for _i in range(366 * 2):
            candidate = datetime.combine(
                candidate_date, self.first_run_time, tzinfo=tz
            )
            if candidate > after and self._runs_on(candidate_date):
                return candidate
            candidate_date += timedelta(days=1)
        # No matching day within the scan window (e.g. an ANNUALLY schedule
        # anchored on 29 February can be up to four years out). Rather than
        # silently reporting "unscheduled", log it so a dead schedule is
        # diagnosable.
        logger.warning(
            'compute_next_run: no matching day found within %d days for '
            '%s(pk=%s, schedule_type=%s); treating as unscheduled',
            366 * 2, type(self).__name__, self.pk, self.schedule_type,
        )
        return None

    def _runs_on(self, day):
        """True if the calendar schedule fires on ``day`` (a date)."""
        if self.first_run_date and day < self.first_run_date:
            return False
        if self.schedule_type == self.ScheduleType.WEEKLY:
            # days_of_week uses 0=Sunday; date.weekday() uses 0=Monday.
            return (day.weekday() + 1) % 7 in self.days_of_week
        anchor = self.first_run_date
        if anchor is None:
            # clean() requires first_run_date for calendar types, but
            # objects.create()/loaddata/shell edits can bypass validation.
            return False
        if day.day != anchor.day:
            return False
        months_apart = (day.year - anchor.year) * 12 + day.month - anchor.month
        cadence = {
            self.ScheduleType.MONTHLY: 1,
            self.ScheduleType.QUARTERLY: 3,
            self.ScheduleType.SEMI_ANNUALLY: 6,
            self.ScheduleType.ANNUALLY: 12,
        }[self.schedule_type]
        return months_apart % cadence == 0

    def create_celery_schedule(self):
        """
        Creates and returns the appropriate django-celery-beat schedule object
        (IntervalSchedule or CrontabSchedule) based on the schedule_type.
        """
        if self.schedule_type == self.ScheduleType.INTERVAL:
            return self._create_interval_schedule()
        else:
            return self._create_crontab_schedule()

    def _create_interval_schedule(self):
        """Create an IntervalSchedule for INTERVAL type schedules."""
        from django_celery_beat.models import IntervalSchedule

        period_mapping = {
            self.IntervalUnit.MINUTES: IntervalSchedule.MINUTES,
            self.IntervalUnit.HOURS: IntervalSchedule.HOURS,
            self.IntervalUnit.DAYS: IntervalSchedule.DAYS,
        }

        schedule, __ = IntervalSchedule.objects.get_or_create(
            every=self.interval_value,
            period=period_mapping[self.interval_unit],
        )
        return schedule

    def _create_crontab_schedule(self):
        """Create a CrontabSchedule for all non-INTERVAL schedule types."""
        from django_celery_beat.models import CrontabSchedule

        hour = self.first_run_time.hour
        minute = self.first_run_time.minute
        day = self.first_run_date.day if self.first_run_date else 1
        month = self.first_run_date.month if self.first_run_date else 1

        if self.schedule_type == self.ScheduleType.WEEKLY:
            schedule, __ = CrontabSchedule.objects.get_or_create(
                minute=str(minute),
                hour=str(hour),
                day_of_week=','.join(
                    str(d) for d in sorted(self.days_of_week)
                ),
                day_of_month='*',
                month_of_year='*',
                timezone=self.timezone,
            )
            return schedule

        # MONTHLY, QUARTERLY, SEMI_ANNUALLY, ANNUALLY all share the same
        # crontab shape — they differ only in which months to run.
        if self.schedule_type == self.ScheduleType.MONTHLY:
            month_of_year = '*'
        elif self.schedule_type == self.ScheduleType.QUARTERLY:
            # Every 3 months starting from `month`, wrapping around December.
            months = [str((month - 1 + i * 3) % 12 + 1) for i in range(4)]
            month_of_year = ','.join(sorted(months, key=int))
        elif self.schedule_type == self.ScheduleType.SEMI_ANNUALLY:
            months = [str(month), str((month - 1 + 6) % 12 + 1)]
            month_of_year = ','.join(sorted(months, key=int))
        elif self.schedule_type == self.ScheduleType.ANNUALLY:
            month_of_year = str(month)
        else:
            raise ValueError(
                f'Unsupported schedule_type: {self.schedule_type}'
            )

        schedule, __ = CrontabSchedule.objects.get_or_create(
            minute=str(minute),
            hour=str(hour),
            day_of_month=str(day),
            day_of_week='*',
            month_of_year=month_of_year,
            timezone=self.timezone,
        )
        return schedule
