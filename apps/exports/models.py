import reversion
from django.db import models
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from reversion.models import Version

from apps.commcare.models import BaseModel, RunBaseModel
from apps.schedules.mixin import ScheduleMixin


class ExportConfigBase(ScheduleMixin, BaseModel):
    name = models.CharField(max_length=100)
    account = models.ForeignKey(
        'commcare.CommCareAccount',
        on_delete=models.PROTECT,
    )
    database = models.ForeignKey('db.Database', on_delete=models.PROTECT)
    config_file = models.FileField(upload_to='export-configs/')
    batch_size = models.PositiveIntegerField(
        default=500,
        help_text=_(
            'How many cases to fetch at a time from CommCare. Try increasing '
            'this number if your export gets stuck.'
        ),
    )
    extra_args = models.TextField(blank=True)

    class Meta:
        abstract = True

    @property
    def latest_version(self):
        return Version.objects.get_for_object(self).first()

    @property
    def details_url(self):
        raise NotImplementedError

    def save(self, **kwargs):
        with reversion.create_revision():
            super().save(**kwargs)


@reversion.register()
class ExportConfig(ExportConfigBase):
    SCHEDULED_TASK = 'apps.exports.tasks.run_scheduled_export_task'

    project = models.ForeignKey(
        'commcare.CommCareProject',
        on_delete=models.PROTECT,
    )

    @property
    def details_url(self):
        return reverse('exports:export_details', args=[self.id])

    def __str__(self):
        return f'{self.name} - {self.project}'

    @property
    def run_url(self):
        return reverse('exports:run_export', args=[self.id])

    @property
    def edit_url(self):
        return reverse('exports:edit_export_config', args=[self.id])

    @property
    def last_run_log_url(self):
        run = self.last_run
        return None if run is None else reverse(
            'exports:run_log',
            args=[run.id],
        )


@reversion.register()
class MultiProjectExportConfig(ExportConfigBase):
    SCHEDULED_TASK = 'apps.exports.tasks.run_scheduled_multi_export_task'

    projects = models.ManyToManyField('commcare.CommCareProject')

    @property
    def details_url(self):
        return reverse('exports:multi_export_details', args=[self.id])

    def __str__(self):
        return f'{self.name} - {self.projects.count()} projects'

    def get_last_run_for_project(self, project):
        try:
            return MultiProjectPartialExportRun.objects.filter(
                parent_run__base_export_config=self,
                project=project,
            ).order_by('-created_at')[0]
        except IndexError:
            return None

    def get_projects_display_short(self):
        project_count = self.projects.count()
        if project_count > 2:
            return mark_safe(
                f'{self.projects.all()[0].domain}<br>+ {project_count - 1} more'
            )
        else:
            return mark_safe(
                '<br>'.join(p.domain for p in self.projects.all())
            )

    @property
    def run_url(self):
        return reverse('exports:run_multi_export', args=[self.id])

    @property
    def edit_url(self):
        return reverse('exports:edit_multi_export_config', args=[self.id])

    @property
    def last_run_log_url(self):
        run = self.last_run
        return None if run is None else reverse(
            'exports:multi_run_log',
            args=[run.id],
        )


class ExportRunBase(RunBaseModel):
    class Status(models.TextChoices):
        QUEUED = 'queued', _('Queued')
        STARTED = 'started', _('Started')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        SKIPPED = 'skipped', _('Skipped')
        MULTIPLE = 'multiple', _('Multiple statuses')

    status = models.CharField(
        max_length=10,
        default=Status.QUEUED,
        choices=Status.choices,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.base_export_config.name} ({self.created_at})'


class ExportRun(ExportRunBase):
    base_export_config = models.ForeignKey(
        ExportConfig,
        on_delete=models.CASCADE,
        related_name='runs',
    )
    export_config_version = models.ForeignKey(
        Version,
        on_delete=models.CASCADE,
        null=True,
    )


class MultiProjectExportRun(ExportRunBase):
    base_export_config = models.ForeignKey(
        MultiProjectExportConfig,
        on_delete=models.CASCADE,
        related_name='runs',
    )
    export_config_version = models.ForeignKey(
        Version,
        on_delete=models.CASCADE,
        null=True,
    )


class MultiProjectPartialExportRun(ExportRunBase):
    parent_run = models.ForeignKey(
        MultiProjectExportRun,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='partial_runs',
    )
    project = models.ForeignKey(
        'commcare.CommCareProject',
        on_delete=models.CASCADE,
    )
