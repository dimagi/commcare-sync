"""Tests for the launcher's startup maintenance (see
commcare_sync/launcher/maintenance.py)."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django_q.brokers import get_broker
from django_q.models import OrmQ, Schedule
from unmagic import use

from apps.exports.models import (
    ExportRun,
    MultiProjectExportRun,
    MultiProjectPartialExportRun,
)
from apps.exports.tests.fixtures import export_config, multi_export_config
from apps.forwarding.models import ForwardingConfig, ForwardingRun
from apps.forwarding.tests.fixtures import destination
from apps.refreshes.models import RefreshRun
from apps.refreshes.tests.fixtures import refresh_config
from commcare_sync.launcher.maintenance import (
    ABANDONED_MESSAGE,
    DISPATCHER_FUNC,
    RUN_MODELS,
    clear_stale_queue_locks,
    ensure_dispatcher_schedule,
    reap_stale_runs,
)
from tests.fixtures import commcare_project, database


@use('db')
class TestEnsureDispatcherSchedule:
    def test_migration_created_the_schedule(self):
        # Nothing to do: apps/schedules/migrations/0001 already ran.
        assert ensure_dispatcher_schedule() is False
        assert Schedule.objects.filter(func=DISPATCHER_FUNC).count() == 1

    def test_recreates_a_deleted_schedule(self):
        Schedule.objects.filter(func=DISPATCHER_FUNC).delete()

        assert ensure_dispatcher_schedule() is True

        schedule = Schedule.objects.get(func=DISPATCHER_FUNC)
        assert schedule.name == 'Run due schedules'
        assert schedule.schedule_type == Schedule.MINUTES
        assert schedule.minutes == 1

    def test_is_idempotent(self):
        Schedule.objects.filter(func=DISPATCHER_FUNC).delete()

        ensure_dispatcher_schedule()
        ensure_dispatcher_schedule()

        assert Schedule.objects.filter(func=DISPATCHER_FUNC).count() == 1


@use('db')
class TestClearStaleQueueLocks:
    def test_locked_task_becomes_deliverable_again(self):
        broker = get_broker()
        broker.enqueue('payload')
        dequeued = broker.dequeue()
        assert [payload for _id, payload in dequeued] == ['payload']
        # The broker holds the row for Conf.RETRY, so it is no longer queued.
        assert broker.queue_size() == 0
        assert broker.lock_size() == 1

        assert clear_stale_queue_locks() == 1

        assert broker.queue_size() == 1
        assert [payload for _id, payload in broker.dequeue()] == ['payload']

    def test_ignores_a_task_that_is_already_deliverable(self):
        broker = get_broker()
        broker.enqueue('payload')

        assert clear_stale_queue_locks() == 0

        assert broker.queue_size() == 1

    def test_no_tasks_is_not_an_error(self):
        assert OrmQ.objects.count() == 0
        assert clear_stale_queue_locks() == 0


def _stale_cutoff_offset():
    """Something comfortably older than the task timeout."""
    return timedelta(seconds=settings.Q_CLUSTER['timeout'] + 60)


def _age_run(run, age):
    """Backdate a run: created_at/started_at are auto/derived fields."""
    began_at = timezone.now() - age
    type(run).objects.filter(pk=run.pk).update(
        created_at=began_at,
        started_at=began_at if run.started_at else None,
    )


def _make_run(model, status, age, started=True, log=None):
    run = model.objects.create(
        status=status,
        started_at=timezone.now() if started else None,
        log=log,
        **_run_parent_kwargs(model),
    )
    _age_run(run, age)
    return run


def _run_parent_kwargs(model):
    """The required FK for each run model."""
    if model is ExportRun:
        return {'base_export_config': export_config()}
    if model is MultiProjectExportRun:
        return {'base_export_config': multi_export_config()}
    if model is MultiProjectPartialExportRun:
        return {'project': commcare_project()}
    if model is ForwardingRun:
        return {'forwarding_config': _forwarding_config()}
    if model is RefreshRun:
        return {'refresh_config': refresh_config()}
    raise AssertionError(f'No parent configured for {model.__name__}')


def _forwarding_config():
    return ForwardingConfig.objects.create(
        name='Forwarding Config',
        database=database(),
        destination=destination(),
        query='SELECT * FROM test',
    )


@use('db', export_config, multi_export_config, refresh_config, destination)
class TestReapStaleRuns:
    def test_reaps_every_run_model(self):
        old = _stale_cutoff_offset()
        runs = [
            _make_run(model, model.Status.STARTED, old) for model in RUN_MODELS
        ]
        assert len(runs) == 5

        assert reap_stale_runs() == 5

        for run in runs:
            run.refresh_from_db()
            assert run.status == type(run).Status.FAILED, type(run).__name__
            assert ABANDONED_MESSAGE in run.log
            assert run.completed_at is not None

    def test_reaps_a_run_still_queued_from_before_the_timeout(self):
        run = _make_run(
            ExportRun,
            ExportRun.Status.QUEUED,
            _stale_cutoff_offset(),
            started=False,
        )

        assert reap_stale_runs() == 1

        run.refresh_from_db()
        assert run.status == ExportRun.Status.FAILED

    def test_appends_to_an_existing_log(self):
        run = _make_run(
            RefreshRun,
            RefreshRun.Status.STARTED,
            _stale_cutoff_offset(),
            log='Started refreshing public.view1',
        )

        reap_stale_runs()

        run.refresh_from_db()
        assert run.log.startswith('Started refreshing public.view1\n')
        assert ABANDONED_MESSAGE in run.log

    def test_leaves_young_runs_alone(self):
        started = _make_run(
            ExportRun, ExportRun.Status.STARTED, timedelta(minutes=5)
        )
        queued = _make_run(
            RefreshRun,
            RefreshRun.Status.QUEUED,
            timedelta(minutes=5),
            started=False,
        )

        assert reap_stale_runs() == 0

        started.refresh_from_db()
        queued.refresh_from_db()
        assert started.status == ExportRun.Status.STARTED
        assert queued.status == RefreshRun.Status.QUEUED
        assert started.log is None

    def test_leaves_finished_runs_alone(self):
        old = _stale_cutoff_offset()
        finished = [
            _make_run(ExportRun, ExportRun.Status.COMPLETED, old, log='done'),
            _make_run(ExportRun, ExportRun.Status.FAILED, old, log='boom'),
            _make_run(RefreshRun, RefreshRun.Status.SKIPPED, old),
        ]

        assert reap_stale_runs() == 0

        for run in finished:
            status_before = run.status
            run.refresh_from_db()
            assert run.status == status_before
            assert ABANDONED_MESSAGE not in (run.log or '')
