from unittest.mock import patch

from unmagic import use

from .fixtures import forwarding_config

from ..models import ForwardingConfig, ForwardingRun
from ..tasks import run_forwarding_task, run_scheduled_forwarding_task


class TestForwardingTask:
    @use(forwarding_config)
    def test_redelivered_task_does_not_redo_the_work(self):
        config = forwarding_config()
        run = ForwardingRun.objects.create(
            config=config, status=ForwardingRun.Status.STARTED
        )

        with patch('apps.forwarding.tasks.run_forwarding') as mock_run:
            run_forwarding_task(run.id)

        mock_run.assert_not_called()


class TestScheduledForwardingTask:
    @use(forwarding_config)
    def test_scheduled_forwarding_runs_inline_without_a_second_task(self):
        """The scheduled task does the work; it does not enqueue a hop."""
        config = forwarding_config()

        with patch('apps.forwarding.tasks.run_forwarding') as mock_run, \
                patch('apps.schedules.dispatch.async_task') as mock_async:
            run_scheduled_forwarding_task(config.id)

        mock_async.assert_not_called()
        assert mock_run.call_count == 1
        assert mock_run.call_args.args[0].config == config

    @use(forwarding_config)
    def test_scheduled_forwarding_skipped_while_a_run_is_active(self):
        config = forwarding_config()
        ForwardingRun.objects.create(
            config=config, status=ForwardingRun.Status.STARTED
        )

        with patch('apps.forwarding.tasks.run_forwarding') as mock_run:
            run_scheduled_forwarding_task(config.id)

        mock_run.assert_not_called()
        assert config.runs.count() == 1

    @use('db')
    def test_scheduled_forwarding_missing_config_returns_none(self):
        missing_id = ForwardingConfig.objects.count() + 1

        with patch('apps.forwarding.tasks.run_forwarding') as mock_run:
            result = run_scheduled_forwarding_task(missing_id)

        assert result is None
        mock_run.assert_not_called()
