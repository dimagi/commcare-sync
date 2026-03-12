import reversion
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from reversion.models import Version

from apps.commcare.models import BaseModel, RunBaseModel
from apps.db.models import Database as ExportDatabase
from apps.exports.templatetags.dateformat_tags import readable_timedelta
from apps.schedules.mixin import ScheduleMixin


@reversion.register()
class RefreshConfig(ScheduleMixin, BaseModel):
    """Configuration for scheduled materialized view refreshes."""

    CELERY_TASK = 'apps.refreshes.tasks.run_scheduled_refresh_task'
    PERIODIC_TASK_PREFIX = 'Refresh materialized views'

    name = models.CharField(max_length=100)
    database = models.ForeignKey(
        ExportDatabase,
        on_delete=models.CASCADE,
        help_text=_('PostgreSQL database connection'),
    )
    materialized_views = models.JSONField(
        default=list,
        blank=True,
        help_text=_(
            'List of materialized views (schema.view_name) to refresh in order'
        ),
    )
    concurrently = models.BooleanField(
        default=False,
        help_text=_(
            'Use REFRESH MATERIALIZED VIEW CONCURRENTLY to avoid locking '
            'the view during refresh. Requires a unique index on each view.'
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    @property
    def last_run(self):
        return (
            self.runs.exclude(status=RefreshRun.Status.QUEUED)
            .order_by('-created_at')
            .first()
        )

    @property
    def latest_version(self):
        return Version.objects.get_for_object(self).first()

    @property
    def details_url(self):
        return reverse('refreshes:refresh_details', args=[self.id])

    def save(self, *args, **kwargs):
        with reversion.create_revision():
            super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        if self.database_id:
            conn_str = self.database.connection_string
            if not conn_str.startswith('postgresql://'):
                raise ValidationError({
                    'database': _(
                        'Only PostgreSQL databases are supported for '
                        'materialized view refreshes.'
                    )
                })

        if not self.materialized_views:
            raise ValidationError({
                'materialized_views': _(
                    'At least one materialized view must be selected.'
                )
            })


class RefreshRun(RunBaseModel):
    """Record of a single materialized view refresh run."""

    refresh_config = models.ForeignKey(
        RefreshConfig,
        on_delete=models.CASCADE,
        related_name='runs',
    )
    refresh_config_version = models.ForeignKey(
        Version,
        on_delete=models.SET_NULL,
        null=True,
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_(
            'When the refresh actually started running. It may have been '
            'created/queued earlier.'
        ),
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    triggered_from_ui = models.BooleanField(null=True, default=None)
    triggering_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    log = models.TextField(null=True, blank=True)
    view_results = models.JSONField(default=dict)

    def __str__(self):
        return f'{self.refresh_config.name} ({self.created_at})'

    @property
    def duration(self):
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        else:
            return None

    def get_duration_display(self):
        return readable_timedelta(self.duration)

    def mark_skipped(self):
        if not self.status == RefreshRun.Status.QUEUED:
            raise ValueError(
                _('Can\'t mark a run "skipped" after it has been started.')
            )
        self.status = RefreshRun.Status.SKIPPED
        self.completed_at = timezone.now()
        self.save()
