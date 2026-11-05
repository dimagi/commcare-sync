from unmagic import use

from tests.fixtures import authed_client

from ..models import ForwardingRun
from .fixtures import forwarding_config


@use(authed_client, forwarding_config)
class TestForwardingRunStatus:
    def test_failed_run_is_complete(self):
        run = ForwardingRun.objects.create(
            config=forwarding_config(), status=ForwardingRun.Status.FAILED
        )

        response = authed_client().get(run.status_url)

        assert response.json() == {
            'status': 'failed',
            'label': 'Failed',
            'tone': 'danger',
            'complete': True,
        }
