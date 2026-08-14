from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from unmagic import use

from apps.commcare.models import RunBaseModel
from apps.exports.models import (
    MultiProjectExportRun,
    MultiProjectPartialExportRun,
)
from apps.exports.tests.fixtures import multi_export_config
from apps.forwarding.models import ForwardingRun
from apps.forwarding.tests.fixtures import destination, forwarding_config
from apps.schedules.tasks import (
    REAP_MARGIN,
    reap_stale_runs,
    run_due_schedules,
)
from tests.fixtures import commcare_project, database

TIMEOUT = settings.Q_CLUSTER['timeout']


def _cutoff_age():
    """Seconds after which a STARTED run is old enough to be reaped."""
    return TIMEOUT + REAP_MARGIN.total_seconds()


def _run(started_ago, status=RunBaseModel.Status.STARTED):
    config = forwarding_config()
    run = ForwardingRun.objects.create(config=config, status=status)
    ForwardingRun.objects.filter(pk=run.pk).update(
        started_at=timezone.now() - started_ago
    )
    run.refresh_from_db()
    return config, run


def _partial_run(started_ago, status=RunBaseModel.Status.STARTED):
    parent = MultiProjectExportRun.objects.create(config=multi_export_config())
    run = MultiProjectPartialExportRun.objects.create(
        parent_run=parent, project=commcare_project(), status=status
    )
    MultiProjectPartialExportRun.objects.filter(pk=run.pk).update(
        started_at=timezone.now() - started_ago
    )
    run.refresh_from_db()
    return run


@use(
    database,
    destination,
    forwarding_config,
    multi_export_config,
    commcare_project,
)
class TestReapStaleRuns:
    def test_reaps_started_run_older_than_the_timeout(self):
        config, run = _run(timedelta(seconds=_cutoff_age() + 60))

        assert reap_stale_runs() == 1

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.TIMEOUT
        assert run.completed_at is not None
        assert 'timed out' in run.log
        assert config.has_active_run is False

    def test_reaps_stale_multi_project_partial_export_run(self):
        # MultiProjectPartialExportRun is a separate model from the
        # MultiProjectExportRun that owns it, so it needs its own
        # coverage: dropping it from `RUN_MODELS` would leave the
        # suite green otherwise.
        run = _partial_run(timedelta(seconds=_cutoff_age() + 60))

        assert reap_stale_runs() == 1

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.TIMEOUT
        assert run.completed_at is not None
        assert 'timed out' in run.log

    def test_leaves_started_run_inside_the_timeout(self):
        _, run = _run(timedelta(seconds=TIMEOUT - 60))

        assert reap_stale_runs() == 0

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.STARTED

    def test_leaves_started_run_inside_the_reap_margin(self):
        # Older than the raw timeout but still within REAP_MARGIN of it:
        # the margin exists precisely so this is not reaped, in case the
        # scheduler's clock runs slightly behind the worker's.
        _, run = _run(timedelta(seconds=TIMEOUT + 30))

        assert reap_stale_runs() == 0

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.STARTED

    def test_leaves_queued_runs_of_any_age(self):
        _, run = _run(timedelta(days=7), status=RunBaseModel.Status.QUEUED)

        assert reap_stale_runs() == 0

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.QUEUED

    def test_appends_to_an_existing_log_without_erasing_it(self):
        _, run = _run(timedelta(seconds=_cutoff_age() + 60))
        ForwardingRun.objects.filter(pk=run.pk).update(log='partial output')

        reap_stale_runs()

        run.refresh_from_db()
        assert run.log.startswith('partial output')
        assert 'timed out' in run.log

    def test_run_due_schedules_reaps_first(self):
        config, run = _run(timedelta(seconds=_cutoff_age() + 60))

        run_due_schedules()

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.TIMEOUT
