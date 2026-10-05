from datetime import timedelta

from django.apps import apps
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
    RUN_MODELS,
    reap_stale_runs,
    run_due_schedules,
)
from tests.fixtures import commcare_project, database

TASK_TIMEOUT = timedelta(
    seconds=settings.Q_CLUSTER['timeout'],  # type: ignore[arg-type]
)
# Comfortably older than the reaper's cutoff (the task timeout plus
# REAP_MARGIN).
STALE = TASK_TIMEOUT + REAP_MARGIN + timedelta(minutes=1)


def _run(started_ago, status=RunBaseModel.Status.STARTED):
    config = forwarding_config()
    run = ForwardingRun.objects.create(config=config, status=status)
    ForwardingRun.objects.filter(pk=run.pk).update(
        started_at=timezone.now() - started_ago
    )
    run.refresh_from_db()
    return run


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
        run = _run(STALE)

        assert reap_stale_runs() == 1

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.TIMEOUT
        assert run.completed_at is not None
        assert 'This run did not finish.' in run.log
        assert run.config.has_active_run is False

    def test_reaps_stale_multi_project_partial_export_run(self):
        # MultiProjectPartialExportRun is a separate model from the
        # MultiProjectExportRun that owns it, and has no config, so
        # reaping it gets its own test.
        run = _partial_run(STALE)

        assert reap_stale_runs() == 1

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.TIMEOUT
        assert run.completed_at is not None
        assert 'This run did not finish.' in run.log

    def test_leaves_started_run_inside_the_timeout(self):
        run = _run(TASK_TIMEOUT - timedelta(minutes=1))

        assert reap_stale_runs() == 0

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.STARTED

    def test_leaves_started_run_inside_the_reap_margin(self):
        # Older than the raw timeout but still within REAP_MARGIN of it:
        # the margin exists precisely so this is not reaped, in case the
        # scheduler's clock runs slightly behind the worker's.
        run = _run(TASK_TIMEOUT + timedelta(seconds=30))

        assert reap_stale_runs() == 0

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.STARTED

    def test_leaves_queued_runs_of_any_age(self):
        run = _run(timedelta(days=7), status=RunBaseModel.Status.QUEUED)

        assert reap_stale_runs() == 0

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.QUEUED

    def test_appends_to_an_existing_log_without_erasing_it(self):
        run = _run(STALE)
        ForwardingRun.objects.filter(pk=run.pk).update(log='partial output')

        reap_stale_runs()

        run.refresh_from_db()
        assert run.log.startswith('partial output')
        assert 'This run did not finish.' in run.log

    def test_run_due_schedules_reaps_first(self):
        run = _run(STALE)

        run_due_schedules()

        run.refresh_from_db()
        assert run.status == RunBaseModel.Status.TIMEOUT


def test_run_models_lists_every_concrete_run_model():
    # A run model missing from RUN_MODELS is never reaped, and a killed
    # run would block its config forever.
    concrete_run_models = {
        model for model in apps.get_models()
        if issubclass(model, RunBaseModel)
    }
    assert set(RUN_MODELS) == concrete_run_models


def test_every_run_model_indexes_what_the_reaper_filters_on():
    for run_model in RUN_MODELS:
        indexed = [tuple(index.fields) for index in run_model._meta.indexes]
        assert ('status', 'started_at') in indexed, run_model.__name__
