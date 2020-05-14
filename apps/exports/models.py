from django.conf import settings
from django.db import models
from django.utils.safestring import mark_safe
from apps.commcare.models import BaseModel
from apps.exports.templatetags.dateformat_tags import readable_timedelta


class ExportDatabase(BaseModel):
    name = models.CharField(max_length=100)
    connection_string = models.CharField(max_length=100)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class ExportConfigBase(BaseModel):
    name = models.CharField(max_length=100)
    account = models.ForeignKey('commcare.CommCareAccount', on_delete=models.CASCADE)
    database = models.ForeignKey(ExportDatabase, on_delete=models.CASCADE)
    config_file = models.FileField(upload_to='export-configs/')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        abstract = True

    @property
    def last_run(self):
        return self.runs.order_by('-created_at')[0] if self.runs.exists() else None


class ExportConfig(ExportConfigBase):
    project = models.ForeignKey('commcare.CommCareProject', on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.name} - {self.project}'


class ExportRunBase(BaseModel):
    COMPLETED = 'completed'
    STARTED = 'started'
    FAILED = 'failed'
    STATUS_CHOICES = (
        (STARTED, 'started'),
        (COMPLETED, 'completed'),
        (FAILED, 'failed'),
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, default='started', choices=STATUS_CHOICES)
    log = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.export_config.name} ({self.created_at})'

    @property
    def duration(self):
        if self.completed_at:
            return self.completed_at - self.created_at
        else:
            return None

    def get_duration_display(self):
        return readable_timedelta(self.duration)

    def get_log_html(self):
        formatted_log = str(self.log).replace('\n', '<br>') if self.log else ''
        return mark_safe(formatted_log)


class ExportRun(ExportRunBase):
    export_config = models.ForeignKey(ExportConfig, on_delete=models.CASCADE, related_name='runs')
