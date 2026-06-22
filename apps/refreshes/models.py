import reversion
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from reversion.models import Version

from apps.commcare.models import BaseModel, RunBaseModel
from apps.db.models import Database
from apps.schedules.mixin import ScheduleMixin


@reversion.register()
class RefreshConfig(ScheduleMixin, BaseModel):
    """Configuration for scheduled materialized view refreshes."""

    CELERY_TASK = 'apps.refreshes.tasks.run_scheduled_refresh_task'
    PERIODIC_TASK_PREFIX = 'Refresh materialized views'

    name = models.CharField(max_length=100)
    database = models.ForeignKey(
        Database,
        on_delete=models.PROTECT,
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
    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    @property
    def latest_version(self):
        return Version.objects.get_for_object(self).first()

    @property
    def details_url(self):
        return reverse('refreshes:refresh_details', args=[self.id])

    @property
    def run_url(self):
        return reverse('refreshes:run_refresh', args=[self.id])

    @property
    def edit_url(self):
        return reverse('refreshes:edit_refresh_config', args=[self.id])

    @property
    def last_run_log_url(self):
        run = self.last_run
        return None if run is None else reverse('refreshes:run_log', args=[run.id])

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
        on_delete=models.CASCADE,
        null=True,
    )
    view_results = models.JSONField(default=dict)

    def __str__(self):
        return f'{self.refresh_config.name} ({self.created_at})'
