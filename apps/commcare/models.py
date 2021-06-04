from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _


class BaseModel(models.Model):
    """
    Base model that includes default created / updated timestamps.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


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


class CommCareAccount(BaseModel):
    server = models.ForeignKey(CommCareServer, on_delete=models.CASCADE)
    username = models.EmailField(
        max_length=100,
        help_text=_("The email address you use to sign into CommCare HQ")
    )
    api_key = models.CharField(
        max_length=40,
        help_text=_('Your API key is available under "My Account Settings" in CommCare.')
    )
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('server', 'username')

    def __str__(self):
        return self.username
