from django.urls import reverse
from unmagic import use

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
        response = htmx_client().get(reverse(
            'forwarding:run_history_table',
            args=[forwarding_config().id],
        ))
        assert response.status_code == 200

    @use(authed_client, forwarding_config)
    def test_non_htmx_request_rejected(self):
        response = authed_client().get(reverse(
            'forwarding:run_history_table',
            args=[forwarding_config().id],
        ))
        assert response.status_code == 400
