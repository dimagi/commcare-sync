from unittest.mock import patch

from unmagic import use

from ..models import ForwardingRun
from ..tasks import run_forwarding_task
from .fixtures import forwarding_config as _forwarding_config


@use(_forwarding_config)
@patch('apps.forwarding.tasks.run_forwarding')
def test_run_forwarding_task(mock_run_forwarding):
    config = _forwarding_config()
    fwd_run = ForwardingRun.objects.create(forwarding_config=config)

    result = run_forwarding_task(fwd_run.id)

    assert result == fwd_run.id
    mock_run_forwarding.assert_called_once_with(fwd_run)


@use('db')
@patch('apps.forwarding.tasks.run_forwarding')
def test_run_forwarding_task_nonexistent_run(mock_run_forwarding):
    result = run_forwarding_task(99999)

    assert result is None
    mock_run_forwarding.assert_not_called()


@use(_forwarding_config)
@patch('apps.forwarding.tasks.run_forwarding')
def test_run_forwarding_task_skips_a_run_that_already_finished(
    mock_run_forwarding,
):
    # A redelivered task — e.g. after a restart cleared the queue lock on a
    # run that the same restart had already reaped — must not resurrect it.
    config = _forwarding_config()
    fwd_run = ForwardingRun.objects.create(
        forwarding_config=config,
        status=ForwardingRun.Status.FAILED,
    )

    result = run_forwarding_task(fwd_run.id)

    assert result is None
    mock_run_forwarding.assert_not_called()
    fwd_run.refresh_from_db()
    assert fwd_run.status == ForwardingRun.Status.FAILED
