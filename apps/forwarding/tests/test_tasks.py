from unittest.mock import patch

from unmagic import use

from .fixtures import forwarding_config

from ..models import ForwardingRun
from ..tasks import run_forwarding_task


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

    @use('db')
    def test_missing_run_logs_and_returns(self, caplog):
        assert run_forwarding_task(999999) is None
        assert 'no longer exists' in caplog.text
