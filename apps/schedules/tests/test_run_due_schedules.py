from datetime import timedelta
from unittest.mock import patch

import pytest
from django.apps import apps
from django.utils import timezone
from django.utils.module_loading import import_string
from unmagic import fixture, use

from apps.forwarding.models import ForwardingConfig, ForwardingRun
from apps.forwarding.tests.fixtures import destination
from apps.refreshes.models import RefreshConfig
from apps.schedules.mixin import ScheduleMixin
from apps.schedules.tasks import CONFIG_MODELS, run_due_schedules
from apps.schedules.tests.consts import SCHEDULED
from tests.fixtures import database


@fixture
def mock_async():
    with patch('apps.schedules.dispatch.async_task') as mock:
        yield mock


def _make_due(model, overdue_by=timedelta(minutes=5), **overrides):
    """Create a config of ``model`` that came due ``overdue_by`` ago."""
    defaults = {'name': f'Due {model.__name__}', **SCHEDULED}
    defaults.update(overrides)
    cfg = model.objects.create(**defaults)
    # Back-date via the queryset so save() doesn't recompute next_run_at.
    model.objects.filter(pk=cfg.pk).update(
        next_run_at=timezone.now() - overdue_by
    )
    cfg.refresh_from_db()
    return cfg


def due_forwarding_config(overdue_by=timedelta(minutes=5), **overrides):
    return _make_due(
        ForwardingConfig,
        overdue_by=overdue_by,
        database=database(),
        destination=destination(),
        query='SELECT * FROM test',
        **overrides,
    )


def due_refresh_config(overdue_by=timedelta(minutes=5), **overrides):
    return _make_due(
        RefreshConfig, overdue_by=overdue_by, database=database(), **overrides
    )


@use(database, destination, mock_async)
class TestRunDueSchedules:

    def test_enqueues_due_config_and_advances_next_run(self):
        cfg = due_forwarding_config()

        launched = run_due_schedules()

        run = cfg.runs.get()
        assert run.triggered_from_ui is False
        mock_async().assert_called_once_with(
            'apps.forwarding.tasks.run_forwarding_task',
            run.id,
        )
        assert launched == [f'ForwardingConfig:{cfg.id}']
        cfg.refresh_from_db()
        assert cfg.next_run_at > timezone.now()

    def test_next_run_is_anchored_on_the_due_time_not_on_now(self):
        # A schedule must stay on its original grid: a 30-minute schedule
        # that came due 5 minutes ago next runs 30 minutes after it was
        # due, not 30 minutes after the dispatcher got around to it.
        # Anchoring on `now` would let each cycle absorb the dispatcher's
        # lag and drift the schedule forward indefinitely.
        cfg = due_forwarding_config()
        due_at = cfg.next_run_at

        run_due_schedules()

        cfg.refresh_from_db()
        assert cfg.next_run_at == due_at + timedelta(minutes=30)

    def test_missed_runs_are_skipped_rather_than_replayed(self):
        cfg = due_forwarding_config(overdue_by=timedelta(days=1))
        due_at = cfg.next_run_at

        launched = run_due_schedules()

        assert launched == [f'ForwardingConfig:{cfg.id}']
        assert mock_async().call_count == 1
        cfg.refresh_from_db()
        assert cfg.next_run_at > timezone.now()
        elapsed = cfg.next_run_at - due_at
        # Validate that `next_run_at` is still in line with the original
        # schedule.
        assert elapsed % timedelta(minutes=30) == timedelta(0)

    def test_reservation_lost_to_a_concurrent_dispatcher_does_not_enqueue(
        self,
    ):
        # Two dispatcher invocations can overlap (a slow cycle, or a
        # second cluster). Advancing next_run_at is the reservation, so the
        # loser - whose conditional update matches no row - must not
        # enqueue a duplicate run.
        cfg = due_forwarding_config()

        def reserve_it_first(*args, **kwargs):
            ForwardingConfig.objects.filter(pk=cfg.pk).update(
                next_run_at=timezone.now() + timedelta(minutes=30)
            )
            return timezone.now() + timedelta(minutes=25)

        with patch.object(
            ForwardingConfig, 'compute_next_run', side_effect=reserve_it_first
        ):
            launched = run_due_schedules()

        mock_async().assert_not_called()
        assert launched == []

    def test_a_config_that_cannot_be_advanced_is_never_enqueued(self):
        # Reserving before enqueueing means a config whose next_run_at
        # can't be computed is skipped outright. Enqueueing first would
        # leave it due forever, dispatching a fresh run every minute.
        cfg = due_forwarding_config()
        ForwardingConfig.objects.filter(pk=cfg.pk).update(
            timezone='America/Newyork'
        )

        launched = run_due_schedules()

        mock_async().assert_not_called()
        assert launched == []

    def test_config_with_an_active_run_is_skipped_but_advanced(self):
        cfg = due_forwarding_config()
        ForwardingRun.objects.create(
            config=cfg, status=ForwardingRun.Status.STARTED
        )

        launched = run_due_schedules()

        mock_async().assert_not_called()
        assert launched == []
        assert cfg.runs.count() == 1
        cfg.refresh_from_db()
        assert cfg.next_run_at > timezone.now()

    def test_skips_configs_that_are_not_due(self):
        due_forwarding_config()
        ForwardingConfig.objects.update(
            next_run_at=timezone.now() + timedelta(hours=1)
        )

        run_due_schedules()

        mock_async().assert_not_called()

    def test_skips_disabled_schedules(self):
        due_forwarding_config(schedule_enabled=False)

        run_due_schedules()

        mock_async().assert_not_called()

    def test_a_failing_reaper_does_not_stop_scheduling(self):
        cfg = due_forwarding_config()

        with patch(
            'apps.schedules.tasks.reap_stale_runs',
            side_effect=RuntimeError('lock timeout'),
        ):
            launched = run_due_schedules()

        assert launched == [f'ForwardingConfig:{cfg.id}']

    def test_poison_config_does_not_starve_later_configs(self):
        # A config whose schedule fields are malformed enough to make
        # compute_next_run raise must not stop other due configs -
        # including ones for other models - from being enqueued and
        # advanced.
        #
        # ForwardingConfig is dispatched before RefreshConfig in
        # CONFIG_MODELS. A ForwardingConfig whose timezone is
        # invalid reaches ZoneInfo(...) inside compute_next_run and
        # raises - this must not stop the RefreshConfig below it (or any
        # other due ForwardingConfig) from being enqueued.
        poison = due_forwarding_config()
        ForwardingConfig.objects.filter(pk=poison.pk).update(
            timezone='America/Newyork'
        )
        healthy_forwarding = due_forwarding_config()
        healthy_refresh = due_refresh_config()

        launched = run_due_schedules()

        assert launched == [
            f'ForwardingConfig:{healthy_forwarding.id}',
            f'RefreshConfig:{healthy_refresh.id}',
        ]

        healthy_forwarding.refresh_from_db()
        assert healthy_forwarding.next_run_at > timezone.now()
        healthy_refresh.refresh_from_db()
        assert healthy_refresh.next_run_at > timezone.now()

        # The poison config is left as-is (still due) rather than
        # silently marked as handled.
        poison.refresh_from_db()
        assert poison.next_run_at < timezone.now()

    def test_dispatches_the_configured_task_for_a_refresh_config(self):
        # test_enqueues_due_config_and_advances_next_run covers this for
        # ForwardingConfig; this is the equivalent check for
        # RefreshConfig, whose RUN_TASK differs.
        cfg = due_refresh_config()

        launched = run_due_schedules()

        mock_async().assert_called_once_with(
            'apps.refreshes.tasks.run_refresh_task',
            cfg.runs.get().id,
        )
        assert launched == [f'RefreshConfig:{cfg.id}']


def test_config_models_lists_every_scheduled_config_model():
    # A config model missing from CONFIG_MODELS is never scheduled.
    scheduled_config_models = {
        model for model in apps.get_models()
        if issubclass(model, ScheduleMixin)
    }
    assert set(CONFIG_MODELS) == scheduled_config_models


@pytest.mark.parametrize('config_model', CONFIG_MODELS)
def test_run_task_names_a_task(config_model):
    # The dispatcher names the task by its dotted path, so a renamed task
    # would otherwise only fail when a worker tries to import it.
    assert callable(import_string(config_model.RUN_TASK))
