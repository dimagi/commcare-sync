import re

from django.urls import reverse
from unmagic import fixture, use

from apps.exports.models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)
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


@fixture
@use('db')
def multi_export_config():
    yield MultiProjectExportConfig.objects.create(
        name='Multi Export Config',
        account=commcare_account(),
        database=database(),
    )


@fixture
@use('db')
def export_run():
    yield ExportRun.objects.create(
        base_export_config=export_config(),
        status=ExportRun.Status.COMPLETED,
    )


@fixture
@use('db')
def multi_export_run():
    yield MultiProjectExportRun.objects.create(
        base_export_config=multi_export_config(),
        status=MultiProjectExportRun.Status.COMPLETED,
    )


class TestExportConfigBaseProperties:
    @use(export_config)
    def test_export_config_edit_url(self):
        config = export_config()
        expected = reverse('exports:edit_export_config', args=[config.id])
        assert config.edit_url == expected

    @use(multi_export_config)
    def test_multi_export_config_edit_url(self):
        config = multi_export_config()
        expected = reverse(
            'exports:edit_multi_export_config', args=[config.id]
        )
        assert config.edit_url == expected

    @use(export_config)
    def test_last_run_log_url_none_when_no_run(self):
        assert export_config().last_run_log_url is None

    @use(multi_export_config)
    def test_last_run_log_url_none_when_no_run_multi(self):
        assert multi_export_config().last_run_log_url is None


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


class TestConfigTableView:
    @use(authed_client)
    def test_requires_login(self):
        client = authed_client()
        client.logout()
        response = client.get(reverse('exports:config_table'))
        assert response.status_code == 302

    @use(authed_client)
    def test_returns_200(self):
        response = authed_client().get(reverse('exports:config_table'))
        assert response.status_code == 200

    @use(authed_client, export_config)
    def test_config_appears(self):
        response = authed_client().get(reverse('exports:config_table'))
        assert export_config().name in response.content.decode()

    @use(authed_client, commcare_project, commcare_account, database)
    def test_pagination_default_page_size_10(self):
        proj = commcare_project()
        acct = commcare_account()
        db_ = database()
        for i in range(15):
            ExportConfig.objects.create(
                name=f'Config {i}',
                project=proj,
                account=acct,
                database=db_,
            )
        response = authed_client().get(reverse('exports:config_table'))
        assert response.status_code == 200
        shown = response.content.decode().count('Config ')
        assert shown == 10

    @use(authed_client, commcare_project, commcare_account, database)
    def test_page_size_param_respected(self):
        proj = commcare_project()
        acct = commcare_account()
        db_ = database()
        for i in range(25):
            ExportConfig.objects.create(
                name=f'Config {i}',
                project=proj,
                account=acct,
                database=db_,
            )
        response = authed_client().get(
            reverse('exports:config_table'), {'page_size': 20}
        )
        assert response.status_code == 200
        shown = response.content.decode().count('Config ')
        assert shown == 20

    @use(authed_client, export_config)
    def test_etag_match_returns_no_swap(self):
        export_config()
        client = authed_client()
        # First request — get a valid etag
        response = client.get(reverse('exports:config_table'))
        assert response.status_code == 200
        match = re.search(
            r'data-etag="([a-f0-9]+)"', response.content.decode()
        )
        assert match, 'data-etag not found in response'
        etag = match.group(1)

        # Second request with matching etag — should return HX-Reswap: none
        response2 = client.get(
            reverse('exports:config_table'), {'etag': etag}
        )
        assert response2.status_code == 200
        assert response2.get('HX-Reswap') == 'none'

    @use(authed_client, export_config)
    def test_etag_mismatch_returns_full_content(self):
        config = export_config()
        response = authed_client().get(
            reverse('exports:config_table'), {'etag': 'stale'}
        )
        assert response.status_code == 200
        assert response.get('HX-Reswap') is None
        assert config.name in response.content.decode()

    @use(authed_client, export_config)
    def test_page_clamped_when_out_of_range(self):
        export_config()
        response = authed_client().get(
            reverse('exports:config_table'), {'page': 999}
        )
        assert response.status_code == 200


class TestRunLogView:
    @use(authed_client, export_run)
    def test_requires_login(self):
        run = export_run()
        client = authed_client()
        client.logout()
        response = client.get(reverse('exports:run_log', args=[run.id]))
        assert response.status_code == 302

    @use(authed_client, export_run)
    def test_returns_log_content(self):
        run = export_run()
        run.log = 'Test log output'
        run.save()
        response = authed_client().get(
            reverse('exports:run_log', args=[run.id])
        )
        assert response.status_code == 200
        assert 'Test log output' in response.content.decode()

    @use(authed_client)
    def test_404_for_invalid_run(self):
        response = authed_client().get(reverse('exports:run_log', args=[9999]))
        assert response.status_code == 404


class TestMultiRunLogView:
    @use(authed_client, multi_export_run)
    def test_requires_login(self):
        run = multi_export_run()
        client = authed_client()
        client.logout()
        response = client.get(reverse('exports:multi_run_log', args=[run.id]))
        assert response.status_code == 302

    @use(authed_client, multi_export_run)
    def test_returns_log_content(self):
        run = multi_export_run()
        run.log = 'Multi log output'
        run.save()
        response = authed_client().get(
            reverse('exports:multi_run_log', args=[run.id])
        )
        assert response.status_code == 200
        assert 'Multi log output' in response.content.decode()


class TestExportsHomeViewUpdated:
    @use(authed_client)
    def test_home_includes_config_table_div(self):
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        assert 'id="exports-config-table"' in response.content.decode()

    @use(authed_client, multi_export_config)
    def test_multi_config_appears_in_merged_table(self):
        config = multi_export_config()
        response = authed_client().get(reverse('exports:home'))
        assert config.name in response.content.decode()
