from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.web.templatetags.dateformat_tags import readable_timedelta


class BaseModel(models.Model):
    """
    Base model that includes default created / updated timestamps.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class RunBaseModel(BaseModel):
    """
    Base model for all run records (exports, forwarding, refreshes).
    """
    class Status(models.TextChoices):
        QUEUED = 'queued', _('Queued')
        STARTED = 'started', _('Started')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        SKIPPED = 'skipped', _('Skipped')

    status = models.CharField(
        max_length=10,
        default=Status.QUEUED,
        choices=Status.choices,
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_(
            'When the run actually started. It may have been '
            'created/queued earlier.'
        ),
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    triggered_from_ui = models.BooleanField(null=True, default=None)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    log = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def has_log(self):
        return self.status in {self.Status.COMPLETED, self.Status.FAILED}

    @property
    def duration(self):
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None

    def get_duration_display(self):
        return readable_timedelta(self.duration)

    def mark_skipped(self):
        if self.status != self.Status.QUEUED:
            raise ValueError(
                _('Can\'t mark a run "skipped" after it has been started.')
            )
        self.status = self.Status.SKIPPED
        self.completed_at = timezone.now()
        self.save()


class CommCareServer(BaseModel):
    name = models.CharField(max_length=100, default='CommCare HQ')
    url = models.CharField(
        max_length=100, default=settings.COMMCARE_DEFAULT_SERVER,
        unique=True,
    )

    def __str__(self):
        return f'{self.name} ({self.url})'

    def get_url_base(self):
        """
        Returns the url with no trailing slash.
        """
        return self.url.rstrip('/')


class CommCareProject(BaseModel):
    server = models.ForeignKey(CommCareServer, on_delete=models.CASCADE)
    domain = models.CharField(
        max_length=100,
        help_text=_("Your CommCare domain (available from the URL)")
    )

    class Meta:
        unique_together = ('server', 'domain')

    def __str__(self):
        return f'{self.domain} ({self.server.name})'

    @property
    def url(self):
        return f'{self.server.get_url_base()}/a/{self.domain}/'

    def is_in_use(self):
        return (
            self.exportconfig_set.exists()
            or self.multiprojectexportconfig_set.exists()
        )


class CommCareAccount(BaseModel):
    server = models.ForeignKey(CommCareServer, on_delete=models.CASCADE)
    username = models.EmailField(
        max_length=100,
        help_text=_("The email address you use to sign into CommCare HQ")
    )
    api_key_encrypted = models.CharField(
        max_length=255,
        help_text=_('Your API key is available under "My Account Settings" in CommCare.')
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    class Meta:
        unique_together = ('server', 'username')

    def __str__(self):
        return self.username

    @property
    def api_key(self):
        """Decrypt and return the API key."""
        if not self.api_key_encrypted:
            return ''

        fernet_keys = (  # Include rotated keys for decryption
            key.encode() if isinstance(key, str) else key
            for key in settings.FERNET_KEYS
        )
        fernet = MultiFernet([Fernet(k) for k in fernet_keys])
        decrypted = fernet.decrypt(self.api_key_encrypted.encode())
        return decrypted.decode()

    @api_key.setter
    def api_key(self, value):
        """Encrypt and store the API key."""
        if not value:
            self.api_key_encrypted = ''
            return

        key = settings.FERNET_KEYS[0]  # Encrypt using the current key
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        encrypted = fernet.encrypt(value.encode())
        self.api_key_encrypted = encrypted.decode()

    def is_in_use(self):
        return (
            self.exportconfig_set.exists()
            or self.multiprojectexportconfig_set.exists()
        )
