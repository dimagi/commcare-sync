from django.conf import settings
from django.db import models


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
    url = models.CharField(max_length=100, default=settings.COMMCARE_DEFAULT_SERVER)

    def __str__(self):
        return f'{self.name} ({self.url})'


class CommCareProject(BaseModel):
    server = models.ForeignKey(CommCareServer, on_delete=models.CASCADE)
    domain = models.CharField(max_length=100)

    class Meta:
        unique_together = ('server', 'domain')

    def __str__(self):
        return f'{self.domain} ({self.server.name})'

    @property
    def url(self):
        return f'{self.server.url}a/{self.domain}/'

class CommCareAccount(BaseModel):
    server = models.ForeignKey(CommCareServer, on_delete=models.CASCADE)
    username = models.CharField(max_length=100)
    api_key = models.CharField(max_length=40)

    def __str__(self):
        return f'{self.username} ({self.server.name})'
