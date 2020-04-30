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


class CommCareProject(BaseModel):
    server = models.ForeignKey(CommCareServer, on_delete=models.CASCADE)
    domain = models.CharField(max_length=100)


class CommCareAccount(BaseModel):
    server = models.ForeignKey(CommCareServer, on_delete=models.CASCADE)
    username = models.CharField(max_length=100)
    api_key = models.CharField(max_length=40)


class ExportDatabase(BaseModel):
    connection_string = models.CharField(max_length=100)


class ExportConfig(BaseModel):
    project = models.ForeignKey(CommCareProject, on_delete=models.CASCADE)
    account = models.ForeignKey(CommCareAccount, on_delete=models.CASCADE)
    database = models.ForeignKey(ExportDatabase, on_delete=models.CASCADE)
    config_file = models.FileField(upload_to='export-configs/', null=True, blank=True)
