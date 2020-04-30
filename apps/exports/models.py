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

    def __str__(self):
        return f'{self.domain} ({self.server.name})'


class CommCareAccount(BaseModel):
    server = models.ForeignKey(CommCareServer, on_delete=models.CASCADE)
    username = models.CharField(max_length=100)
    api_key = models.CharField(max_length=40)

    def __str__(self):
        return f'{self.username} ({self.server.name})'


class ExportDatabase(BaseModel):
    name = models.CharField(max_length=100)
    connection_string = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class ExportConfig(BaseModel):
    name = models.CharField(max_length=100)
    project = models.ForeignKey(CommCareProject, on_delete=models.CASCADE)
    account = models.ForeignKey(CommCareAccount, on_delete=models.CASCADE)
    database = models.ForeignKey(ExportDatabase, on_delete=models.CASCADE)
    config_file = models.FileField(upload_to='export-configs/', null=True, blank=True)

    def __str__(self):
        return f'{self.name} - {self.project}'

    @property
    def last_run(self):
        return self.runs.order_by('-created_at')[0] if self.runs.exists() else None


class ExportRun(BaseModel):

    STATUS_CHOICES = (
        ('started', 'started'),
        ('completed', 'completed'),
        ('failed', 'failed'),
    )
    export_config = models.ForeignKey(ExportConfig, on_delete=models.CASCADE, related_name='runs')
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, default='started', choices=STATUS_CHOICES)

    def __str__(self):
        return f'{self.export_config.name} ({self.created_at})'
