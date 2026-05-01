from unittest.mock import patch

from unmagic import fixture, use

from ..models import RefreshRun
from ..tasks import run_refresh_task, run_scheduled_refresh_task

_refresh_config = fixture('refresh_config')


@use(_refresh_config)
@patch('apps.refreshes.tasks.run_refresh')
def test_run_refresh_task(mock_run_refresh):
    config = _refresh_config()
    refresh_run = RefreshRun.objects.create(refresh_config=config)

    result = run_refresh_task(refresh_run.id)

    assert result == refresh_run.id
    mock_run_refresh.assert_called_once_with(refresh_run)


@use('db')
@patch('apps.refreshes.tasks.run_refresh')
def test_run_refresh_task_nonexistent_run(mock_run_refresh):
    result = run_refresh_task(99999)

    assert result is None
    mock_run_refresh.assert_not_called()


@use(_refresh_config)
@patch('apps.refreshes.tasks.run_refresh')
def test_run_scheduled_refresh_task(mock_run_refresh):
    config = _refresh_config()
    result = run_scheduled_refresh_task(config.id)

    assert result is not None
    mock_run_refresh.assert_called_once()

    run = RefreshRun.objects.get(id=result)
    assert run.refresh_config == config
    assert run.triggered_from_ui is False


@use(_refresh_config)
@patch('apps.refreshes.tasks.run_refresh')
def test_run_scheduled_refresh_task_skips_if_queued(mock_run_refresh):
    config = _refresh_config()
    RefreshRun.objects.create(
        refresh_config=config,
        status=RefreshRun.Status.QUEUED,
    )

    result = run_scheduled_refresh_task(config.id)

    assert result is None
    mock_run_refresh.assert_not_called()


@use(_refresh_config)
@patch('apps.refreshes.tasks.run_refresh')
def test_run_scheduled_refresh_task_skips_if_started(mock_run_refresh):
    config = _refresh_config()
    RefreshRun.objects.create(
        refresh_config=config,
        status=RefreshRun.Status.STARTED,
    )

    result = run_scheduled_refresh_task(config.id)

    assert result is None
    mock_run_refresh.assert_not_called()


@use('db')
@patch('apps.refreshes.tasks.run_refresh')
def test_run_scheduled_refresh_task_nonexistent_config(mock_run_refresh):
    result = run_scheduled_refresh_task(99999)

    assert result is None
    mock_run_refresh.assert_not_called()
