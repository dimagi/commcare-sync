from unittest.mock import patch

import pytest
from unmagic import fixture, use

from apps.schedules.mixin import ScheduleMixin
from tests.fixtures import (
    commcare_account,
    commcare_project,
    database,
    regular_user,
)

from ..models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)
from ..tasks import (
    run_all_exports_task,
    run_export_task,
    run_multi_project_export_task,
    run_scheduled_export_task,
)

# Schedule kwargs that make a config "non-paused" — ScheduleMixin.is_paused
# is True unless the config has a schedule and schedule_enabled is True.
SCHEDULED = {
    'schedule_type': ScheduleMixin.ScheduleType.INTERVAL,
    'interval_value': 30,
    'interval_unit': ScheduleMixin.IntervalUnit.MINUTES,
}


@fixture
@use('db')
def export_config():
    yield ExportConfig.objects.create(
        name='Test Export',
        project=commcare_project(),
        account=commcare_account(),
        database=database(),
        **SCHEDULED,
    )


@fixture
@use('db')
def paused_export_config():
    # No schedule_type → ScheduleMixin.is_paused returns True.
    yield ExportConfig.objects.create(
        name='Paused Export',
        project=commcare_project(),
        account=commcare_account(),
        database=database(),
    )


@fixture
@use('db')
def multi_export_config():
    yield MultiProjectExportConfig.objects.create(
        name='Test Multi Export',
        account=commcare_account(),
        database=database(),
        **SCHEDULED,
    )


class TestRunAllExportsTask:
    @use(export_config, multi_export_config)
    @patch('apps.schedules.dispatch.async_task')
    def test_enqueues_one_run_per_config(self, mock_async):
        config = export_config()
        multi = multi_export_config()

        run_all_exports_task()

        runs = ExportRun.objects.filter(config=config)
        multi_runs = MultiProjectExportRun.objects.filter(config=multi)
        assert runs.count() == 1
        assert multi_runs.count() == 1

        mock_async.assert_any_call(run_export_task, runs.first().id)
        mock_async.assert_any_call(
            run_multi_project_export_task, multi_runs.first().id
        )
        assert mock_async.call_count == 2

    @use(export_config, regular_user)
    @patch('apps.schedules.dispatch.async_task')
    def test_marks_ui_attribution(self, mock_async):
        config = export_config()
        user = regular_user()

        run_all_exports_task(user_id=user.id)

        run = ExportRun.objects.get(config=config)
        assert run.triggered_from_ui is True
        assert run.triggered_by == user

    @use(paused_export_config)
    @patch('apps.schedules.dispatch.async_task')
    def test_skips_paused_configs(self, mock_async):
        config = paused_export_config()

        run_all_exports_task()

        assert not ExportRun.objects.filter(config=config).exists()
        mock_async.assert_not_called()

    @pytest.mark.parametrize('status', [
        ExportRun.Status.QUEUED,
        ExportRun.Status.STARTED,
    ])
    @use(export_config)
    @patch('apps.schedules.dispatch.async_task')
    def test_skips_configs_with_active_runs(self, mock_async, status):
        config = export_config()
        # A run is already queued or in progress. "Run All" must not stack
        # another run on top, the same way the per-row "Run" button disables
        # itself for an active run.
        ExportRun.objects.create(
            config=config,
            triggered_from_ui=False,
            status=status,
        )

        run_all_exports_task()

        assert ExportRun.objects.filter(config=config).count() == 1
        mock_async.assert_not_called()

    @use(export_config)
    @patch('apps.schedules.dispatch.async_task')
    def test_handles_unknown_user_id(self, mock_async):
        config = export_config()
        run_all_exports_task(user_id=999999)

        run = ExportRun.objects.get(config=config)
        # A user_id was supplied, so it's a UI trigger even though the user
        # could not be resolved. triggered_by is None because the user is gone.
        assert run.triggered_from_ui is True
        assert run.triggered_by is None
        mock_async.assert_called_once()

    @use(export_config)
    @patch('apps.schedules.dispatch.async_task')
    def test_cli_trigger_with_no_user_is_not_marked_ui_triggered(
        self, mock_async
    ):
        # manage.py run_all_exports calls this with user_id=None. It must
        # not be recorded as a UI trigger with no user behind it.
        config = export_config()

        run_all_exports_task()

        run = ExportRun.objects.get(config=config)
        assert run.triggered_from_ui is False
        assert run.triggered_by is None


class TestScheduledExportTask:
    @use(export_config)
    def test_scheduled_export_runs_inline_without_a_second_task(self):
        """The scheduled task does the work; it does not enqueue a hop."""
        config = export_config()

        with (
            patch('apps.exports.tasks.run_export') as mock_run,
            patch('apps.schedules.dispatch.async_task') as mock_async,
        ):
            run_scheduled_export_task(config.id)

        mock_async.assert_not_called()
        assert mock_run.call_count == 1
        assert mock_run.call_args.args[0].config == config

    @use(export_config)
    def test_scheduled_export_skipped_while_a_run_is_started(self):
        config = export_config()
        ExportRun.objects.create(
            config=config, status=ExportRun.Status.STARTED
        )

        with patch('apps.exports.tasks.run_export') as mock_run:
            run_scheduled_export_task(config.id)

        mock_run.assert_not_called()
        assert config.runs.count() == 1


class TestExportTask:
    @use(export_config)
    def test_run_export_task_defaults_start_over_to_false(self):
        config = export_config()
        run = ExportRun.objects.create(config=config)

        with patch('apps.exports.tasks.run_export') as mock_run:
            mock_run.return_value = run
            run_export_task(run.id)

        assert mock_run.call_args.args[1] is False

    @use('db')
    def test_missing_run_logs_and_returns(self, caplog):
        assert run_export_task(999999) is None
        assert 'no longer exists' in caplog.text


class TestMultiProjectExportTask:
    @use(multi_export_config)
    def test_redelivered_task_does_not_redo_the_work(self):
        config = multi_export_config()
        run = MultiProjectExportRun.objects.create(
            config=config, status=MultiProjectExportRun.Status.STARTED
        )

        with patch('apps.exports.tasks.run_multi_project_export') as mock_run:
            run_multi_project_export_task(run.id)

        mock_run.assert_not_called()

    @use('db')
    def test_missing_run_logs_and_returns(self, caplog):
        assert run_multi_project_export_task(999999) is None
        assert 'no longer exists' in caplog.text
