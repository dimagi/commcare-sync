import reversion
from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
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
    api_password_encrypted = models.CharField(
        max_length=500,
        blank=True,
        help_text=_('Password for basic authentication'),
    )

    @property
    def api_password(self):
        """Decrypt and return the API password."""
        if not self.api_password_encrypted:
            return ''

        fernet_keys = (  # Include rotated keys for decryption
            key.encode() if isinstance(key, str) else key
            for key in settings.FERNET_KEYS
        )
        fernet = MultiFernet([Fernet(k) for k in fernet_keys])
        decrypted = fernet.decrypt(self.api_password_encrypted.encode())
        return decrypted.decode()

    @api_password.setter
    def api_password(self, value):
        """Encrypt and store the API password."""
        if not value:
            self.api_password_encrypted = ''
            return

        key = settings.FERNET_KEYS[0]  # Encrypt using the current key
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        encrypted = fernet.encrypt(value.encode())
        self.api_password_encrypted = encrypted.decode()

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
    def run_url(self):
        return reverse('forwarding:run_forwarding', args=[self.id])

    @property
    def edit_url(self):
        return reverse('forwarding:edit_forwarding_config', args=[self.id])

    @property
    def last_run_log_url(self):
        run = self.last_run
        return None if run is None else reverse(
            'forwarding:run_log',
            args=[run.id],
        )

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
