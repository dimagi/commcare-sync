import datetime
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.safestring import mark_safe
from apps.commcare.models import BaseModel
from apps.exports.templatetags.dateformat_tags import readable_timedelta


class ExportDatabase(BaseModel):
    name = models.CharField(max_length=100)
    connection_string = models.CharField(max_length=500)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class ExportConfigBase(BaseModel):
    name = models.CharField(max_length=100)
    account = models.ForeignKey('commcare.CommCareAccount', on_delete=models.CASCADE)
    database = models.ForeignKey(ExportDatabase, on_delete=models.CASCADE)
    config_file = models.FileField(upload_to='export-configs/')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    time_between_runs = models.PositiveIntegerField(
        default=settings.COMMCARE_SYNC_EXPORT_PERIODICITY / 60,
        help_text='How regularly to sync this export, in minutes.',
    )
    is_paused = models.BooleanField(default=False,
                                    help_text='Pausing an export will disable automatic syncing. '
                                              'You can still manually run it.')
    extra_args = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def last_run(self):
        return self.runs.order_by('-created_at')[0] if self.runs.exists() else None

    def is_scheduled_to_run(self):
        last_run = self.last_run
        # first time running
        if not last_run:
            return True
        # last run still active
        if not last_run.completed_at:
            return False
        else:
            # run if last run completed before the scheduled time between runs
            next_scheduled_run_time = last_run.completed_at + datetime.timedelta(minutes=self.time_between_runs)
            return timezone.now() > next_scheduled_run_time


class ExportConfig(ExportConfigBase):
    project = models.ForeignKey('commcare.CommCareProject', on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.name} - {self.project}'


class MultiProjectExportConfig(ExportConfigBase):
    projects = models.ManyToManyField('commcare.CommCareProject')

    def __str__(self):
        return f'{self.name} - {self.projects.count()} projects'

    def get_projects_display_short(self):
        project_count = self.projects.count()
        if project_count > 2:
            return mark_safe(f'{self.projects.all()[0].domain}<br>+ {project_count - 1} more')
        else:
            return mark_safe('<br>'.join(p.domain for p in self.projects.all()))


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


class MultiProjectExportRun(ExportRunBase):
    export_config = models.ForeignKey(MultiProjectExportConfig, on_delete=models.CASCADE, related_name='runs')
    project = models.ForeignKey('commcare.CommCareProject', on_delete=models.CASCADE)
