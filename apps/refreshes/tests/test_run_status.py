from unmagic import use

from tests.fixtures import authed_client

from ..models import RefreshRun
from .fixtures import refresh_config


@use(authed_client, refresh_config)
class TestRefreshRunStatus:
    def test_reports_its_own_run(self):
        run = RefreshRun.objects.create(
            config=refresh_config(), status=RefreshRun.Status.FAILED
        )

        response = authed_client().get(run.status_url)

        assert response.json() == {
            'status': 'failed',
            'label': 'Failed',
            'tone': 'danger',
            'complete': True,
        }
