from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from unmagic import use

from apps.forwarding.models import ForwardingConfig
from apps.forwarding.tests.fixtures import destination
from apps.refreshes.models import RefreshConfig
from apps.schedules.mixin import ScheduleMixin
from apps.schedules.tasks import run_due_schedules
from tests.fixtures import database


@use(database, destination)
class TestRunDueSchedules:

    def _due_config(self, **overrides):
        defaults = dict(
            name='Due Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        defaults.update(overrides)
        cfg = ForwardingConfig.objects.create(**defaults)
        ForwardingConfig.objects.filter(pk=cfg.pk).update(
            next_run_at=timezone.now() - timedelta(minutes=5)
        )
        return cfg

    @patch('apps.schedules.tasks.async_task')
    def test_enqueues_due_config_and_advances_next_run(self, mock_async):
        cfg = self._due_config()

        launched = run_due_schedules()

        mock_async.assert_called_once_with(
            'apps.forwarding.tasks.run_scheduled_forwarding_task',
            cfg.id,
            q_options={},
        )
        assert launched == [f'ForwardingConfig:{cfg.id}']
        cfg.refresh_from_db()
        assert cfg.next_run_at > timezone.now()

    @patch('apps.schedules.tasks.async_task')
    def test_skips_configs_that_are_not_due(self, mock_async):
        self._due_config()
        ForwardingConfig.objects.update(
            next_run_at=timezone.now() + timedelta(hours=1)
        )

        run_due_schedules()

        mock_async.assert_not_called()

    @patch('apps.schedules.tasks.async_task')
    def test_skips_disabled_schedules(self, mock_async):
        self._due_config(schedule_enabled=False)
        # Force next_run_at as if it had been set before disabling.
        ForwardingConfig.objects.update(
            next_run_at=timezone.now() - timedelta(minutes=5)
        )

        run_due_schedules()

        mock_async.assert_not_called()


@use(database, destination)
class TestRunDueSchedulesErrorIsolation:
    """A config whose schedule fields are malformed enough to make
    ``compute_next_run`` raise must not stop other due configs -
    including ones for other models - from being enqueued and advanced.
    """

    def _due_config(self, **overrides):
        defaults = dict(
            name='Due Config',
            database=database(),
            destination=destination(),
            query='SELECT * FROM test',
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        defaults.update(overrides)
        cfg = ForwardingConfig.objects.create(**defaults)
        ForwardingConfig.objects.filter(pk=cfg.pk).update(
            next_run_at=timezone.now() - timedelta(minutes=5)
        )
        return cfg

    def _due_refresh_config(self, **overrides):
        defaults = dict(
            name='Due Refresh Config',
            database=database(),
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        defaults.update(overrides)
        cfg = RefreshConfig.objects.create(**defaults)
        RefreshConfig.objects.filter(pk=cfg.pk).update(
            next_run_at=timezone.now() - timedelta(minutes=5)
        )
        return cfg

    @patch('apps.schedules.tasks.async_task')
    def test_poison_config_does_not_starve_later_configs(self, mock_async):
        # ForwardingConfig is dispatched before RefreshConfig in
        # _scheduled_models(). A ForwardingConfig whose timezone is
        # invalid reaches ZoneInfo(...) inside compute_next_run and
        # raises - this must not stop the RefreshConfig below it (or any
        # other due ForwardingConfig) from being enqueued.
        poison = self._due_config()
        ForwardingConfig.objects.filter(pk=poison.pk).update(
            timezone='America/Newyork'
        )
        healthy_forwarding = self._due_config()
        healthy_refresh = self._due_refresh_config()

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


@use(database)
class TestRunDueSchedulesOptionsCopy:
    """RefreshConfig has non-empty SCHEDULED_TASK_OPTIONS, so it's the one
    that actually exercises the dict-copy in run_due_schedules: it proves
    the class-level dict is passed by value, not by reference."""

    def _due_refresh_config(self, **overrides):
        defaults = dict(
            name='Due Refresh Config',
            database=database(),
            schedule_type=ScheduleMixin.ScheduleType.INTERVAL,
            interval_value=30,
            interval_unit=ScheduleMixin.IntervalUnit.MINUTES,
        )
        defaults.update(overrides)
        cfg = RefreshConfig.objects.create(**defaults)
        RefreshConfig.objects.filter(pk=cfg.pk).update(
            next_run_at=timezone.now() - timedelta(minutes=5)
        )
        return cfg

    @patch('apps.schedules.tasks.async_task')
    def test_dispatches_with_non_empty_options_and_does_not_mutate_class_attr(
        self, mock_async
    ):
        cfg = self._due_refresh_config()

        launched = run_due_schedules()

        mock_async.assert_called_once_with(
            'apps.refreshes.tasks.run_scheduled_refresh_task',
            cfg.id,
            q_options={'timeout': 3660},
        )
        assert launched == [f'RefreshConfig:{cfg.id}']

        # The dict handed to async_task must be a copy, not the shared
        # class-level dict, so later dispatches (or mutation by a task)
        # can't leak into or corrupt other configs' options.
        passed_options = mock_async.call_args.kwargs['q_options']
        assert passed_options is not RefreshConfig.SCHEDULED_TASK_OPTIONS
        assert RefreshConfig.SCHEDULED_TASK_OPTIONS == {'timeout': 3660}
