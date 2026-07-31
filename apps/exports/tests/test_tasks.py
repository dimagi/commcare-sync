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
    @patch('apps.exports.tasks.async_task')
    def test_enqueues_one_run_per_config(self, mock_async):
        config = export_config()
        multi = multi_export_config()

        run_all_exports_task()

        runs = ExportRun.objects.filter(base_export_config=config)
        multi_runs = MultiProjectExportRun.objects.filter(
            base_export_config=multi
        )
        assert runs.count() == 1
        assert multi_runs.count() == 1

        mock_async.assert_any_call(
            run_export_task, runs.first().id, start_over=False
        )
        mock_async.assert_any_call(
            run_multi_project_export_task,
            multi_runs.first().id,
            start_over=False,
        )
        assert mock_async.call_count == 2

    @use(export_config, regular_user)
    @patch('apps.exports.tasks.async_task')
    def test_marks_ui_attribution(self, mock_async):
        config = export_config()
        user = regular_user()

        run_all_exports_task(user_id=user.id)

        run = ExportRun.objects.get(base_export_config=config)
        assert run.triggered_from_ui is True
        assert run.triggered_by == user

    @use(paused_export_config)
    @patch('apps.exports.tasks.async_task')
    def test_skips_paused_configs(self, mock_async):
        config = paused_export_config()

        run_all_exports_task()

        assert not ExportRun.objects.filter(
            base_export_config=config
        ).exists()
        mock_async.assert_not_called()

    @pytest.mark.parametrize('status', [
        ExportRun.Status.QUEUED,
        ExportRun.Status.STARTED,
    ])
    @use(export_config)
    @patch('apps.exports.tasks.async_task')
    def test_skips_configs_with_active_runs(self, mock_async, status):
        config = export_config()
        # A run is already queued or in progress. "Run All" must not stack
        # another run on top, the same way the per-row "Run" button disables
        # itself for an active run.
        ExportRun.objects.create(
            base_export_config=config,
            triggered_from_ui=False,
            status=status,
        )

        run_all_exports_task()

        assert ExportRun.objects.filter(
            base_export_config=config
        ).count() == 1
        mock_async.assert_not_called()

    @use(export_config)
    @patch('apps.exports.tasks.async_task')
    def test_handles_unknown_user_id(self, mock_async):
        config = export_config()
        run_all_exports_task(user_id=999999)

        run = ExportRun.objects.get(base_export_config=config)
        assert run.triggered_from_ui is True
        assert run.triggered_by is None
        mock_async.assert_called_once()
