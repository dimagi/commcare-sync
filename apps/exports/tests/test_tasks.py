from unittest.mock import patch

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
from ..tasks import run_all_exports_task

# Schedule kwargs that make a config "non-paused" — adding schedule_type
# triggers signal-based creation of an enabled PeriodicTask, which is what
# ScheduleMixin.is_paused checks.
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


@use(export_config, multi_export_config)
@patch('apps.exports.tasks.run_multi_project_export_task.delay')
@patch('apps.exports.tasks.run_export_task.delay')
def test_run_all_exports_task_enqueues_one_run_per_config(
    mock_run_export, mock_run_multi
):
    config = export_config()
    multi = multi_export_config()

    run_all_exports_task()

    runs = ExportRun.objects.filter(base_export_config=config)
    multi_runs = MultiProjectExportRun.objects.filter(base_export_config=multi)
    assert runs.count() == 1
    assert multi_runs.count() == 1

    mock_run_export.assert_called_once_with(
        runs.first().id, start_over=False
    )
    mock_run_multi.assert_called_once_with(
        multi_runs.first().id, start_over=False
    )


@use(export_config, regular_user)
@patch('apps.exports.tasks.run_multi_project_export_task.delay')
@patch('apps.exports.tasks.run_export_task.delay')
def test_run_all_exports_task_marks_ui_attribution(_mock_run, _mock_multi):
    config = export_config()
    user = regular_user()

    run_all_exports_task(user_id=user.id)

    run = ExportRun.objects.get(base_export_config=config)
    assert run.triggered_from_ui is True
    assert run.triggered_by == user


@use(paused_export_config)
@patch('apps.exports.tasks.run_multi_project_export_task.delay')
@patch('apps.exports.tasks.run_export_task.delay')
def test_run_all_exports_task_skips_paused_configs(mock_run, _mock_multi):
    config = paused_export_config()

    run_all_exports_task()

    assert not ExportRun.objects.filter(base_export_config=config).exists()
    mock_run.assert_not_called()


@use(export_config)
@patch('apps.exports.tasks.run_multi_project_export_task.delay')
@patch('apps.exports.tasks.run_export_task.delay')
def test_run_all_exports_task_skips_configs_with_queued_runs(
    mock_run, _mock_multi
):
    config = export_config()
    # Pre-existing queued run — Run All should not stack another on top.
    ExportRun.objects.create(
        base_export_config=config,
        triggered_from_ui=False,
        status=ExportRun.Status.QUEUED,
    )

    run_all_exports_task()

    assert ExportRun.objects.filter(base_export_config=config).count() == 1
    mock_run.assert_not_called()


@use(export_config)
@patch('apps.exports.tasks.run_multi_project_export_task.delay')
@patch('apps.exports.tasks.run_export_task.delay')
def test_run_all_exports_task_skips_configs_with_started_runs(
    mock_run, _mock_multi
):
    config = export_config()
    # A run already in progress — Run All must not stack another on top, the
    # same way the per-row Run button disables itself for an active run.
    ExportRun.objects.create(
        base_export_config=config,
        triggered_from_ui=False,
        status=ExportRun.Status.STARTED,
    )

    run_all_exports_task()

    assert ExportRun.objects.filter(base_export_config=config).count() == 1
    mock_run.assert_not_called()


@use(export_config)
@patch('apps.exports.tasks.run_multi_project_export_task.delay')
@patch('apps.exports.tasks.run_export_task.delay')
def test_run_all_exports_task_handles_unknown_user_id(mock_run, _mock_multi):
    config = export_config()
    # Pass an id that doesn't correspond to any user — should warn and continue
    # with no attribution.
    run_all_exports_task(user_id=999999)

    run = ExportRun.objects.get(base_export_config=config)
    assert run.triggered_from_ui is True
    assert run.triggered_by is None
    mock_run.assert_called_once()
