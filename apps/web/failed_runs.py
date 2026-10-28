"""
Runs that failed or were interrupted recently, for the banner on every
app page.

Read from the run models rather than Django Q2's task table: task rows
are pruned, run rows are kept, and a run that the launcher found
interrupted at startup has no finished task at all.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.contrib.sessions.backends.base import SessionBase
from django.utils import timezone

from apps.exports.models import MultiProjectPartialExportRun
from apps.schedules.tasks import RUN_MODELS

MAX_ENTRIES = 5
DISMISSED_AT_SESSION_KEY = 'failed_runs_dismissed_at'


@dataclass
class FailedRunEntry:
    label: str
    kind: str
    status: str
    completed_at: datetime


@dataclass
class FailedRuns:
    """
    ``total_count`` counts every run; ``entries`` describes the newest
    ``MAX_ENTRIES`` of them.
    """

    total_count: int
    entries: list[FailedRunEntry]

    def __bool__(self) -> bool:
        return bool(self.entries)

    @property
    def more(self) -> int:
        return self.total_count - len(self.entries)


def recent_failed_runs(since: datetime) -> FailedRuns:
    """
    Runs that failed or were interrupted since ``since``, newest first.
    """
    total_count = 0
    entries = []
    for model in RUN_MODELS:
        owner_field = _owner_field(model)
        failed = model.objects.filter(  # type: ignore[attr-defined]
            status__in=model.FAILED_STATUSES, completed_at__gte=since
        )
        total_count += failed.count()
        newest = failed.select_related(owner_field).order_by('-completed_at')
        for run in newest[:MAX_ENTRIES]:
            entries.append(
                FailedRunEntry(
                    label=_label(run, owner_field),
                    kind=str(model._meta.verbose_name),
                    status=run.get_status_display(),
                    completed_at=run.completed_at,
                )
            )
    entries.sort(key=lambda entry: entry.completed_at, reverse=True)
    return FailedRuns(total_count, entries[:MAX_ENTRIES])


def _owner_field(model: type) -> str:
    # A partial export run belongs to a project; every other run, to a
    # config.
    return 'project' if model is MultiProjectPartialExportRun else 'config'


def _label(run: Any, owner_field: str) -> str:
    owner = getattr(run, owner_field)
    return owner.name if owner_field == 'config' else str(owner)


def dismiss(session: SessionBase) -> None:
    session[DISMISSED_AT_SESSION_KEY] = timezone.now().isoformat()


def dismissed_since(session: SessionBase) -> datetime | None:
    """When the banner was last dismissed in this session, if ever."""
    try:
        return datetime.fromisoformat(session[DISMISSED_AT_SESSION_KEY])
    except (KeyError, ValueError):
        # Nothing this module wrote. A banner shown again beats a page
        # that cannot render.
        return None
