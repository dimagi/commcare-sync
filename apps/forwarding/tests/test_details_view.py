from django.urls import reverse
from unmagic import use

from apps.forwarding.models import ForwardingRun
from tests.fixtures import authed_client, htmx_client

from .fixtures import forwarding_config


@use(authed_client, forwarding_config)
def test_export_details_smoke():
    response = authed_client().get(reverse(
        'forwarding:forwarder_details',
        args=[forwarding_config().id],
    ))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Schedule' in content
    assert 'Run History' in content


class TestForwardingRunHistoryTableEndpoint:
    @use(htmx_client, forwarding_config)
    def test_returns_200(self):
        assert (
            htmx_client()
            .get(
                reverse(
                    'forwarding:run_history_table',
                    args=[forwarding_config().id],
                )
            )
            .status_code
            == 200
        )

    @use(authed_client, forwarding_config)
    def test_non_htmx_request_rejected(self):
        url = reverse(
            'forwarding:run_history_table', args=[forwarding_config().id]
        )
        assert authed_client().get(url).status_code == 400

    @use(htmx_client, forwarding_config)
    def test_status_filter_excludes_unchecked(self):
        config = forwarding_config()
        completed_run = ForwardingRun.objects.create(
            forwarding_config=config,
            status=ForwardingRun.Status.COMPLETED,
        )
        failed_run = ForwardingRun.objects.create(
            forwarding_config=config,
            status=ForwardingRun.Status.FAILED,
        )
        url = reverse('forwarding:run_history_table', args=[config.id])
        content = (
            htmx_client()
            .get(url, QUERY_STRING='status_filter=completed')
            .content.decode()
        )
        # Use log-{id} marker which only appears in rendered run rows
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' not in content

    @use(htmx_client, forwarding_config)
    def test_empty_filter_shows_nothing(self):
        config = forwarding_config()
        run = ForwardingRun.objects.create(
            forwarding_config=config,
            status=ForwardingRun.Status.COMPLETED,
        )
        url = reverse('forwarding:run_history_table', args=[config.id])
        content = htmx_client().get(url).content.decode()
        assert f'log-{run.id}' not in content

    @use(htmx_client, forwarding_config)
    def test_pagination_default_10(self):
        config = forwarding_config()
        for _ in range(15):
            ForwardingRun.objects.create(
                forwarding_config=config,
                status=ForwardingRun.Status.COMPLETED,
            )
        url = reverse('forwarding:run_history_table', args=[config.id])
        response = htmx_client().get(
            url,
            QUERY_STRING='status_filter=completed',
        )
        assert response.status_code == 200
        assert 'pagination' in response.content.decode()
