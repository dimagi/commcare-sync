"""Recent-failed-run lookup for the dismissible dashboard banner.

Reads the run models directly rather than django_q's ``Task`` table: with
the default ``save_limit`` (see ``commcare_sync.launcher.maintenance``) task
rows roll over in hours, whereas run status is authoritative and permanent.
This also means runs marked FAILED by
``commcare_sync.launcher.maintenance.reap_stale_runs`` at startup surface
here too — that is precisely the "a schedule died while you weren't
looking" case the banner exists for, and reaping sets ``completed_at`` to
the reap time (see that function), so filtering on ``completed_at`` catches
both normal failures and reaped ones.
"""

from dataclasses import dataclass
from datetime import datetime

from commcare_sync.launcher.maintenance import RUN_MODELS

# Every run model's config foreign key, in the order checked. Not every run
# model has one of these directly (MultiProjectPartialExportRun links to a
# project instead), so absence just falls through to a generic label.
_CONFIG_FIELD_NAMES = (
    'base_export_config',
    'forwarding_config',
    'refresh_config',
)

MAX_ENTRIES = 5


@dataclass
class FailedRunEntry:
    label: str
    model_name: str
    when: datetime


def _config_field_name(model):
    for field_name in _CONFIG_FIELD_NAMES:
        if hasattr(model, field_name):
            return field_name
    return None


def _label_for(run, config_field_name):
    if config_field_name:
        return getattr(run, config_field_name).name
    if hasattr(run, 'project'):
        return f'{run.project} (partial export)'
    return str(run)


def recent_failed_runs(since):
    """Collect FAILED runs across every run model, newer than ``since``.

    Returns a dict with ``total_count`` (failures across all models, exact)
    and ``entries`` (up to ``MAX_ENTRIES`` :class:`FailedRunEntry`, newest
    first) for display.
    """
    total_count = 0
    entries = []
    for model in RUN_MODELS:
        config_field_name = _config_field_name(model)
        queryset = model.objects.filter(
            status=model.Status.FAILED, completed_at__gte=since
        )
        if config_field_name:
            queryset = queryset.select_related(config_field_name)
        elif hasattr(model, 'project'):
            queryset = queryset.select_related('project')

        total_count += queryset.count()
        for run in queryset.order_by('-completed_at')[:MAX_ENTRIES]:
            entries.append(
                FailedRunEntry(
                    label=_label_for(run, config_field_name),
                    model_name=model._meta.verbose_name,
                    when=run.completed_at,
                )
            )

    entries.sort(key=lambda entry: entry.when, reverse=True)
    return {'total_count': total_count, 'entries': entries[:MAX_ENTRIES]}
