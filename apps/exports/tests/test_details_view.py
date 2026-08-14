from django.urls import reverse
from unmagic import use

from apps.exports.tests.fixtures import export_config, export_config_db_fixture
from tests.fixtures import authed_client, htmx_client


@use(authed_client, export_config_db_fixture)
def test_export_details_smoke():
    response = authed_client().get(reverse(
        'exports:export_details',
        args=[export_config_db_fixture().id],
    ))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Schedule' in content
    assert 'Run History' in content


class TestExportRunHistoryTableEndpoint:
    @use(htmx_client, export_config_db_fixture)
    def test_returns_200(self):
        response = htmx_client().get(reverse(
            'exports:run_history_table',
            args=[export_config_db_fixture().id],
        ))
        assert response.status_code == 200

    @use(authed_client, export_config_db_fixture)
    def test_non_htmx_request_rejected(self):
        response = authed_client().get(reverse(
            'exports:run_history_table',
            args=[export_config_db_fixture().id],
        ))
        assert response.status_code == 400


@use(authed_client, export_config)
def test_run_history_renders_a_notice_element():
    # The poller's non-terminal endings write here rather than into the
    # progress message, which Alpine unmounts when `running` clears.
    response = authed_client().get(export_config().details_url)
    content = response.content.decode()
    assert 'id="run-notice"' in content
    assert 'x-text="notice"' in content
    # Cleared on click, so a stale notice never outlives the next run.
    assert 'notice = &#x27;&#x27;' in content or "notice = ''" in content
