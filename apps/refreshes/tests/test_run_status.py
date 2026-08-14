from django.test import Client
from django.urls import reverse
from unmagic import use

from tests.fixtures import authed_client

from ..models import RefreshRun
from .fixtures import refresh_config


@use(authed_client, refresh_config)
class TestRefreshRunStatus:
    def _run(self, status):
        return RefreshRun.objects.create(
            config=refresh_config(), status=status
        )

    def test_queued_run_is_not_complete(self):
        run = self._run(RefreshRun.Status.QUEUED)
        assert authed_client().get(run.status_url).json() == {
            'status': 'queued',
            'label': 'Queued',
            'complete': False,
        }

    def test_failed_run_is_complete(self):
        run = self._run(RefreshRun.Status.FAILED)
        assert authed_client().get(run.status_url).json() == {
            'status': 'failed',
            'label': 'Failed',
            'complete': True,
        }

    def test_timeout_and_skipped_are_complete(self):
        for status in [RefreshRun.Status.TIMEOUT, RefreshRun.Status.SKIPPED]:
            body = authed_client().get(self._run(status).status_url).json()
            assert body['complete'] is True

    def test_status_url_points_at_the_refreshes_endpoint(self):
        run = self._run(RefreshRun.Status.QUEUED)
        assert run.status_url == reverse('refreshes:run_status', args=[run.id])

    def test_response_is_not_cached(self):
        run = self._run(RefreshRun.Status.QUEUED)
        assert authed_client().get(run.status_url)['Cache-Control'] == 'no-store'

    def test_unknown_run_is_404(self):
        url = reverse('refreshes:run_status', args=[999999])
        assert authed_client().get(url).status_code == 404

    def test_requires_login(self):
        run = self._run(RefreshRun.Status.QUEUED)
        assert Client().get(run.status_url).status_code == 302
