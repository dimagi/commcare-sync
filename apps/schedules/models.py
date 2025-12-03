from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.commcare.models import BaseModel


class Schedule(BaseModel):
    """
    Scheduling configuration for exports and data forwarding.

    This model stores scheduling information and creates the appropriate
    django-celery-beat schedule objects (CrontabSchedule or IntervalSchedule).
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

    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices,
    )

    first_run_date = models.DateField(
        null=True, blank=True, help_text=_("Don't run before this date")
    )
    first_run_time = models.TimeField(
        default='00:00', help_text=_('Time of day for first/recurring runs')
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
    )

    periodic_task = models.OneToOneField(
        'django_celery_beat.PeriodicTask',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='schedule',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.schedule_type == self.ScheduleType.INTERVAL:
            return f'Every {self.interval_value} {self.interval_unit.lower()}'
        elif self.schedule_type == self.ScheduleType.WEEKLY:
            day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
            days = ', '.join(day_names[d] for d in sorted(self.days_of_week))
            return f'Weekly on {days} at {self.first_run_time}'
        elif self.schedule_type == self.ScheduleType.MONTHLY:
            day = self.first_run_date.day if self.first_run_date else '?'
            return f'Monthly on day {day} at {self.first_run_time}'
        elif self.schedule_type == self.ScheduleType.QUARTERLY:
            day = self.first_run_date.day if self.first_run_date else '?'
            return f'Quarterly on day {day} at {self.first_run_time}'
        elif self.schedule_type == self.ScheduleType.SEMI_ANNUALLY:
            day = self.first_run_date.day if self.first_run_date else '?'
            return f'Semi-annually on day {day} at {self.first_run_time}'
        elif self.schedule_type == self.ScheduleType.ANNUALLY:
            day = self.first_run_date.day if self.first_run_date else '?'
            return f'Annually on day {day} at {self.first_run_time}'
        return f'Schedule ({self.schedule_type})'

    def clean(self):
        """Validate that required fields are set based on schedule_type."""
        super().clean()

        if self.schedule_type == self.ScheduleType.INTERVAL:
            # Interval schedules require interval_value and interval_unit
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
            # All crontab schedules (WEEKLY, MONTHLY, QUARTERLY, etc.)
            # require first_run_date
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

            # Weekly schedules also require at least one day of week
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

        schedule, created = IntervalSchedule.objects.get_or_create(
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
            schedule, created = CrontabSchedule.objects.get_or_create(
                minute=str(minute),
                hour=str(hour),
                day_of_week=','.join(
                    str(d) for d in sorted(self.days_of_week)
                ),
                day_of_month='*',
                month_of_year='*',
                timezone=self.timezone,
            )
        elif self.schedule_type == self.ScheduleType.MONTHLY:
            schedule, created = CrontabSchedule.objects.get_or_create(
                minute=str(minute),
                hour=str(hour),
                day_of_month=str(day),
                day_of_week='*',
                month_of_year='*',
                timezone=self.timezone,
            )
        elif self.schedule_type == self.ScheduleType.QUARTERLY:
            months = [str((month - 1 + i * 3) % 12 + 1) for i in range(4)]
            schedule, created = CrontabSchedule.objects.get_or_create(
                minute=str(minute),
                hour=str(hour),
                day_of_month=str(day),
                day_of_week='*',
                month_of_year=','.join(sorted(months, key=int)),
                timezone=self.timezone,
            )
        elif self.schedule_type == self.ScheduleType.SEMI_ANNUALLY:
            months = [str(month), str((month - 1 + 6) % 12 + 1)]
            schedule, created = CrontabSchedule.objects.get_or_create(
                minute=str(minute),
                hour=str(hour),
                day_of_month=str(day),
                day_of_week='*',
                month_of_year=','.join(sorted(months, key=int)),
                timezone=self.timezone,
            )
        elif self.schedule_type == self.ScheduleType.ANNUALLY:
            schedule, created = CrontabSchedule.objects.get_or_create(
                minute=str(minute),
                hour=str(hour),
                day_of_month=str(day),
                day_of_week='*',
                month_of_year=str(month),
                timezone=self.timezone,
            )
        else:
            raise ValueError(
                f'Unsupported schedule_type: {self.schedule_type}'
            )

        return schedule
