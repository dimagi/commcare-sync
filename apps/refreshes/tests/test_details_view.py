from django.urls import reverse
from unmagic import use

from tests.fixtures import authed_client, htmx_client

from .fixtures import refresh_config


@use(authed_client, refresh_config)
def test_export_details_smoke():
    response = authed_client().get(reverse(
        'refreshes:refresh_details',
        args=[refresh_config().id],
    ))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Schedule' in content
    assert 'Run History' in content


class TestRefreshRunHistoryTableEndpoint:
    @use(htmx_client, refresh_config)
    def test_returns_200(self):
        response = htmx_client().get(reverse(
            'refreshes:run_history_table',
            args=[refresh_config().id],
        ))
        assert response.status_code == 200

    @use(authed_client, refresh_config)
    def test_non_htmx_request_rejected(self):
        response = authed_client().get(reverse(
            'refreshes:run_history_table',
            args=[refresh_config().id],
        ))
        assert response.status_code == 400
