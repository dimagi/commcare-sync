import reversion
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from reversion.models import Version

from apps.commcare.models import BaseModel
from apps.exports.templatetags.dateformat_tags import readable_timedelta


class ForwardingDatabase(BaseModel):
    """Database where queries are executed (source)."""

    name = models.CharField(max_length=100)
    connection_string = models.CharField(max_length=500)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )

    def __str__(self):
        return self.name


class ForwardingDestination(BaseModel):
    """API endpoint where query results are forwarded (destination)."""

    name = models.CharField(max_length=100)
    api_url = models.URLField(
        max_length=500, help_text=_('API endpoint URL where data will be sent')
    )
    api_username = models.CharField(
        max_length=100,
        blank=True,
        help_text=_('Username for basic authentication'),
    )
    api_password = models.CharField(
        max_length=200,
        blank=True,
        help_text=_('Password for basic authentication'),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )

    def __str__(self):
        return self.name


@reversion.register()
class ForwardingConfig(BaseModel):
    """Configuration for a data forwarding job."""

    name = models.CharField(max_length=100)
    database = models.ForeignKey(ForwardingDatabase, on_delete=models.CASCADE)
    destination = models.ForeignKey(
        ForwardingDestination, on_delete=models.CASCADE
    )
    query = models.TextField(
        help_text=_(
            'SQL query to execute. Must return exactly one row with one field '
            'containing the payload (typically JSON).'
        )
    )
    query_params = models.TextField(
        blank=True,
        help_text=_(
            'Query parameters (one per line). Mapped to :param1, :param2, '
            'etc. in the query.'
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    schedule = models.ForeignKey(
        'schedules.Schedule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_('Scheduling configuration for automatic forwarding.'),
    )
    is_paused = models.BooleanField(
        default=False,
        help_text=_(
            'Pausing will disable automatic forwarding. You can still '
            'manually run it.'
        ),
    )

    def __str__(self):
        return self.name

    @property
    def last_run(self):
        return (
            self.runs
            .exclude(status=ForwardingRun.Status.QUEUED)
            .order_by('-created_at')
            .first()
        )

    def has_queued_runs(self):
        last_run = self.runs.order_by('-created_at').first()
        if last_run:
            return last_run.status == ForwardingRun.Status.QUEUED
        return False

    @property
    def latest_version(self):
        return Version.objects.get_for_object(self).first()

    @property
    def details_url(self):
        return reverse('forwarding:forwarding_details', args=[self.id])

    def save(self, **kwargs):
        with reversion.create_revision():
            super().save(**kwargs)


class ForwardingRun(BaseModel):
    """Record of a single forwarding run."""

    class Status(models.TextChoices):
        QUEUED = 'queued', _('Queued')
        STARTED = 'started', _('Started')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        SKIPPED = 'skipped', _('Skipped')

    forwarding_config = models.ForeignKey(
        ForwardingConfig,
        on_delete=models.CASCADE,
        related_name='runs',
    )
    forwarding_config_version = models.ForeignKey(
        Version, on_delete=models.CASCADE, null=True
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_(
            'When the forward actually started running. It may have been '
            'created/queued earlier.'
        ),
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    triggered_from_ui = models.BooleanField(null=True, default=None)
    triggering_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    status = models.CharField(
        max_length=10, default=Status.QUEUED, choices=Status.choices
    )
    log = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.forwarding_config.name} ({self.created_at})'

    @property
    def duration(self):
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        else:
            return None

    def get_duration_display(self):
        return readable_timedelta(self.duration)

    def mark_skipped(self):
        if not self.status == ForwardingRun.Status.QUEUED:
            raise Exception(
                _('Can\'t mark a run "skipped" after it has been started.')
            )
        self.status = ForwardingRun.Status.SKIPPED
        self.completed_at = timezone.now()
        self.save()
