from unittest.mock import patch

from unmagic import use

from ..models import RefreshRun
from ..tasks import run_refresh_task
from .fixtures import refresh_config as _refresh_config


@use(_refresh_config)
@patch('apps.refreshes.tasks.run_refresh')
def test_run_refresh_task(mock_run_refresh):
    config = _refresh_config()
    refresh_run = RefreshRun.objects.create(config=config)

    result = run_refresh_task(refresh_run.id)

    assert result == refresh_run.id
    mock_run_refresh.assert_called_once_with(refresh_run)


@use(_refresh_config)
@patch('apps.refreshes.tasks.run_refresh')
def test_redelivered_task_does_not_redo_the_work(mock_run_refresh):
    config = _refresh_config()
    run = RefreshRun.objects.create(
        config=config, status=RefreshRun.Status.STARTED
    )

    result = run_refresh_task(run.id)

    assert result is None
    mock_run_refresh.assert_not_called()


@use('db')
def test_missing_run_logs_and_returns(caplog):
    assert run_refresh_task(999999) is None
    assert 'no longer exists' in caplog.text
