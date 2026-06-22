from django.urls import reverse
from unmagic import use

from apps.exports.models import ExportRun
from apps.exports.tests.fixtures import export_config
from apps.forwarding.models import ForwardingRun
from apps.forwarding.tests.fixtures import forwarding_config
from apps.refreshes.models import RefreshRun
from apps.refreshes.tests.fixtures import refresh_config as _refresh_config
from tests.fixtures import authed_client, regular_client


@use(authed_client, regular_client, export_config, _refresh_config, forwarding_config)
class TestConfigTableRunButtonRendering:
    def test_run_button_present_when_no_active_run(self):
        ec, rc, fc = export_config(), _refresh_config(), forwarding_config()
        for client, config, table_url in [
            (authed_client(), ec, reverse('exports:config_table')),
            (authed_client(), rc, reverse('refreshes:config_table')),
            (regular_client(), fc, reverse('forwarding:config_table')),
        ]:
            response = client.get(table_url)
            assert response.status_code == 200
            assert f'hx-post="{config.run_url}"' in response.content.decode()

    def test_run_button_disabled_when_active_run(self):
        ec, rc, fc = export_config(), _refresh_config(), forwarding_config()
        ExportRun.objects.create(base_export_config=ec, status=ExportRun.Status.QUEUED)
        RefreshRun.objects.create(refresh_config=rc, status=RefreshRun.Status.QUEUED)
        ForwardingRun.objects.create(forwarding_config=fc, status=ForwardingRun.Status.QUEUED)
        for client, config, table_url in [
            (authed_client(), ec, reverse('exports:config_table')),
            (authed_client(), rc, reverse('refreshes:config_table')),
            (regular_client(), fc, reverse('forwarding:config_table')),
        ]:
            response = client.get(table_url)
            content = response.content.decode()
            assert 'btn-outline-success' in content
            assert f'hx-post="{config.run_url}"' not in content

    def test_edit_button_never_disabled(self):
        ec, rc, fc = export_config(), _refresh_config(), forwarding_config()
        ExportRun.objects.create(base_export_config=ec, status=ExportRun.Status.QUEUED)
        RefreshRun.objects.create(refresh_config=rc, status=RefreshRun.Status.QUEUED)
        ForwardingRun.objects.create(forwarding_config=fc, status=ForwardingRun.Status.QUEUED)
        for client, config, table_url in [
            (authed_client(), ec, reverse('exports:config_table')),
            (authed_client(), rc, reverse('refreshes:config_table')),
            (regular_client(), fc, reverse('forwarding:config_table')),
        ]:
            response = client.get(table_url)
            assert config.edit_url in response.content.decode()
