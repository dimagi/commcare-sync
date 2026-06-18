from django.urls import reverse
from unmagic import use

from apps.refreshes.models import RefreshRun
from tests.fixtures import authed_client, htmx_client

from .fixtures import refresh_config as _refresh_config


@use(authed_client, _refresh_config)
def test_export_details_smoke():
    response = authed_client().get(reverse(
        'refreshes:refresh_details',
        args=[_refresh_config().id],
    ))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Schedule' in content
    assert 'Run History' in content


class TestRefreshRunHistoryTableEndpoint:
    @use(htmx_client, _refresh_config)
    def test_returns_200(self):
        assert (
            htmx_client()
            .get(
                reverse(
                    'refreshes:run_history_table', args=[_refresh_config().id]
                )
            )
            .status_code
            == 200
        )

    @use(authed_client, _refresh_config)
    def test_non_htmx_request_rejected(self):
        url = reverse('refreshes:run_history_table', args=[_refresh_config().id])
        assert authed_client().get(url).status_code == 400

    @use(htmx_client, _refresh_config)
    def test_status_filter_excludes_unchecked(self):
        config = _refresh_config()
        completed_run = RefreshRun.objects.create(
            refresh_config=config, status=RefreshRun.Status.COMPLETED
        )
        failed_run = RefreshRun.objects.create(
            refresh_config=config, status=RefreshRun.Status.FAILED
        )
        url = reverse('refreshes:run_history_table', args=[config.id])
        content = (
            htmx_client()
            .get(url, QUERY_STRING='status_filter=completed')
            .content.decode()
        )
        # Use log-{id} marker which only appears in rendered run rows
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' not in content

    @use(htmx_client, _refresh_config)
    def test_empty_filter_shows_nothing(self):
        config = _refresh_config()
        run = RefreshRun.objects.create(
            refresh_config=config, status=RefreshRun.Status.COMPLETED
        )
        url = reverse('refreshes:run_history_table', args=[config.id])
        content = htmx_client().get(url).content.decode()
        assert f'log-{run.id}' not in content

    @use(htmx_client, _refresh_config)
    def test_pagination_default_10(self):
        config = _refresh_config()
        for _ in range(15):
            RefreshRun.objects.create(
                refresh_config=config, status=RefreshRun.Status.COMPLETED
            )
        url = reverse('refreshes:run_history_table', args=[config.id])
        response = htmx_client().get(
            url,
            QUERY_STRING='status_filter=completed',
        )
        assert response.status_code == 200
        assert 'pagination' in response.content.decode()
