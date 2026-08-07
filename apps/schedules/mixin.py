import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


ACTIVE_RUN_STATUSES = frozenset({
    RunBaseModel.Status.QUEUED,
    RunBaseModel.Status.STARTED,
})


class ScheduleMixin(models.Model):
    """
    Abstract model mixin that adds scheduling fields to any config model.

    Concrete models must define:
        SCHEDULED_TASK: str - dotted path to the task run on schedule
        runs: reverse relation manager (e.g. from a ForeignKey on a Run model)
        latest_version: the config's current ``reversion`` Version
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
    schedule_enabled = models.BooleanField(
        default=True,
        help_text=_('Uncheck to pause scheduled runs'),
    )
    next_run_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Snapshot the schedule fields as loaded/constructed, so the
        # post_save handler in `apps/schedules/signals.py` can tell
        # whether a later save actually changed the schedule (as opposed
        # to, for example, a rename).
        self.take_schedule_snapshot()

    def take_schedule_snapshot(self):
        """Record the schedule fields as they currently stand.

        Fields deferred by ``.only()``/``.defer()`` are left out rather
        than read: reading a deferred field triggers a
        ``refresh_from_db()``, which builds another instance, which lands
        back here -- unbounded recursion. ``_schedule_changed`` in
        ``apps/schedules/signals.py`` treats a snapshot that doesn't
        cover every schedule field as "assume it changed", so an
        incomplete snapshot costs a redundant recompute, never a missed
        one.
        """
        deferred = self.get_deferred_fields()
        self._schedule_snapshot = {
            field: getattr(self, field)
            for field in SCHEDULE_FIELDS
            if field not in deferred
        }

    @property
    def has_schedule(self):
        return bool(self.schedule_type)

    @property
    def is_paused(self):
        """True when the config has no active schedule."""
        return not (self.has_schedule and self.schedule_enabled)

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
        """True if a run is queued or started.

        Always queries. This gates dispatch, so it must not be answered
        from a prefetch captured for rendering, which may predate the run
        it is being asked about.
        """
        return self.runs.filter(status__in=ACTIVE_RUN_STATUSES).exists()

    @property
    def has_active_run_cached(self):
        """``has_active_run``, answered from ``_all_runs`` when prefetched.

        For list pages, which prefetch every config's runs and would
        otherwise issue a query per row. Falls back to the real thing when
        there is no prefetch.
        """
        all_runs = getattr(self, '_all_runs', None)
        if all_runs is None:
            return self.has_active_run
        return any(r.status in ACTIVE_RUN_STATUSES for r in all_runs)

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

        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise ValidationError(
                {
                    'timezone': _(
                        '%(timezone)s is not a recognized timezone.'
                    ) % {'timezone': self.timezone}
                }
            )

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


# Fields whose value determines the schedule, i.e. every `ScheduleMixin`
# field except `next_run_at` (which is derived from the others). Used by
# `apps/schedules/signals.py` to decide whether a save actually changed
# the schedule (and so must recompute next_run_at) or merely touched an
# unrelated field (e.g. a rename).
SCHEDULE_FIELDS = frozenset(
    f.name for f in ScheduleMixin._meta.local_fields
) - {'next_run_at'}
