from django.urls import reverse
from unmagic import fixture, use

from apps.exports.models import ExportConfig
from tests.fixtures import (
    authed_client,
    commcare_account,
    commcare_project,
    database,
)


@fixture
@use('db')
def export_config():
    yield ExportConfig.objects.create(
        name='Test Export Config',
        project=commcare_project(),
        account=commcare_account(),
        database=database(),
    )


class TestExportsHomeView:
    @use(authed_client)
    def test_stats_in_context(self):
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        assert 'export_stats' in response.context
        assert 'refresh_stats' in response.context
        assert 'forwarding_stats' in response.context

    @use(authed_client, export_config)
    def test_export_appears_in_list(self):
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        assert export_config().name in response.content.decode()
