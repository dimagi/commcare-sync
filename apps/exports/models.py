import reversion
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from reversion.models import Version

from apps.commcare.models import BaseModel
from apps.exports.scheduling import export_is_scheduled_to_run
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
    batch_size = models.PositiveIntegerField(
        default=500,
        help_text='How many cases to fetch at a time from CommCare. '
                  'Try increasing this number if your export gets stuck.',
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    time_between_runs = models.PositiveIntegerField(
        default=int(settings.COMMCARE_SYNC_EXPORT_PERIODICITY / 60),
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
        runs = self.runs.exclude(status=ExportRun.QUEUED)
        return runs.order_by('-created_at')[0] if runs.exists() else None

    def is_scheduled_to_run(self):
        return export_is_scheduled_to_run(self, self.last_run)

    def has_queued_runs(self):
        if self.runs.exists():
            # Each run will ingest all new data when it is available, so we only need one run at a time.
            # We can therefore ignore all but the latest queued run.
            return self.runs.order_by('-created_at')[0].status == ExportRun.QUEUED
        return False

    @property
    def latest_version(self):
        return Version.objects.get_for_object(self).first()

    @property
    def details_url(self):
        if isinstance(self, ExportConfig):
            return reverse('exports:export_details', args=[self.id])
        elif isinstance(self, MultiProjectExportConfig):
            return reverse('exports:multi_export_details', args=[self.id])
        else:
            raise ValueError(f"Can't find details URL for {self}")

    def save(self, **kwargs):
        with reversion.create_revision():
            super().save(**kwargs)


@reversion.register()
class ExportConfig(ExportConfigBase):
    project = models.ForeignKey('commcare.CommCareProject', on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.name} - {self.project}'


@reversion.register()
class MultiProjectExportConfig(ExportConfigBase):
    projects = models.ManyToManyField('commcare.CommCareProject')

    def __str__(self):
        return f'{self.name} - {self.projects.count()} projects'

    def get_last_run_for_project(self, project):
        try:
            return MultiProjectPartialExportRun.objects.filter(
                parent_run__base_export_config=self,
                project=project
            ).order_by('-created_at')[0]
        except IndexError:
            return None

    def get_projects_display_short(self):
        project_count = self.projects.count()
        if project_count > 2:
            return mark_safe(f'{self.projects.all()[0].domain}<br>+ {project_count - 1} more')
        else:
            return mark_safe('<br>'.join(p.domain for p in self.projects.all()))


class ExportRunBase(BaseModel):
    QUEUED = 'queued'
    STARTED = 'started'
    MULTIPLE = 'multiple'
    COMPLETED = 'completed'
    FAILED = 'failed'
    SKIPPED = 'skipped'
    STATUS_CHOICES = (
        (QUEUED, 'queued'),
        (STARTED, 'started'),
        (COMPLETED, 'completed'),
        (FAILED, 'failed'),
        (MULTIPLE, 'multiple statuses'),  # MultiExport only
        (SKIPPED, 'skipped'),
    )
    started_at = models.DateTimeField(null=True, blank=True, help_text="When the export actually started running. "
                                                                       "It may have been created/queued earlier.")
    completed_at = models.DateTimeField(null=True, blank=True)
    triggered_from_ui = models.NullBooleanField(default=None)
    triggering_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                        on_delete=models.SET_NULL)
    status = models.CharField(max_length=10, default=QUEUED, choices=STATUS_CHOICES)
    log = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.base_export_config.name} ({self.created_at})'

    @property
    def duration(self):
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        else:
            return None

    def get_duration_display(self):
        return readable_timedelta(self.duration)

    def get_log_html(self):
        formatted_log = str(self.log).replace('\n', '<br>') if self.log else ''
        return mark_safe(formatted_log)

    def mark_skipped(self):
        if not self.status == ExportRun.QUEUED:
            raise Exception("Can't mark a run that has been started skipped!")
        self.status = ExportRun.SKIPPED
        self.completed_at = timezone.now()
        self.save()


class ExportRun(ExportRunBase):
    base_export_config = models.ForeignKey(ExportConfig, on_delete=models.CASCADE, related_name='runs')
    export_config_version = models.ForeignKey(Version, on_delete=models.CASCADE, null=True)


class MultiProjectExportRun(ExportRunBase):
    base_export_config = models.ForeignKey(MultiProjectExportConfig, on_delete=models.CASCADE, related_name='runs')
    export_config_version = models.ForeignKey(Version, on_delete=models.CASCADE, null=True)


class MultiProjectPartialExportRun(ExportRunBase):
    parent_run = models.ForeignKey(MultiProjectExportRun, null=True, blank=True, on_delete=models.CASCADE,
                                   related_name='partial_runs')
    project = models.ForeignKey('commcare.CommCareProject', on_delete=models.CASCADE)
