import reversion
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from reversion.models import Version

from apps.commcare.models import BaseModel, RunBaseModel
from apps.db.models import Database
from apps.schedules.mixin import ScheduleMixin


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

    def __str__(self):
        return self.name

    def is_in_use(self):
        return self.forwardingconfig_set.exists()


@reversion.register()
class ForwardingConfig(ScheduleMixin, BaseModel):
    """Configuration for a data forwarding job."""

    CELERY_TASK = 'apps.forwarding.tasks.run_scheduled_forwarding_task'
    PERIODIC_TASK_PREFIX = 'Run forwarding'

    name = models.CharField(max_length=100)
    database = models.ForeignKey(Database, on_delete=models.PROTECT)
    destination = models.ForeignKey(
        ForwardingDestination, on_delete=models.PROTECT
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

    def __str__(self):
        return self.name

    @property
    def latest_version(self):
        return Version.objects.get_for_object(self).first()

    @property
    def details_url(self):
        return reverse('forwarding:forwarder_details', args=[self.id])

    @property
    def edit_url(self):
        return reverse('forwarding:edit_forwarding_config', args=[self.id])

    @property
    def last_run_log_url(self):
        run = self.last_run
        return None if run is None else reverse('forwarding:run_log', args=[run.id])

    def save(self, *args, **kwargs):
        with reversion.create_revision():
            super().save(*args, **kwargs)


class ForwardingRun(RunBaseModel):
    """Record of a single forwarding run."""

    forwarding_config = models.ForeignKey(
        ForwardingConfig,
        on_delete=models.CASCADE,
        related_name='runs',
    )
    forwarding_config_version = models.ForeignKey(
        Version, on_delete=models.CASCADE, null=True
    )

    def __str__(self):
        return f'{self.forwarding_config.name} ({self.created_at})'
