import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.commcare.models import (
    CommCareAccount,
    CommCareProject,
    CommCareServer,
)
from apps.exports.models import (
    ExportConfig,
    ExportDatabase,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='listviewuser', email='lv@example.com', password='pass'
    )


@pytest.fixture
def client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def server(db):
    server, _ = CommCareServer.objects.get_or_create(
        url='https://www.commcarehq.org'
    )
    return server


@pytest.fixture
def project(db, server):
    return CommCareProject.objects.create(server=server, domain='test-domain')


@pytest.fixture
def account(db, server, user):
    return CommCareAccount.objects.create(
        server=server, username='u@example.com', api_key='key', owner=user
    )


@pytest.fixture
def database(db, user):
    return ExportDatabase.objects.create(
        name='TestDB',
        connection_string='postgresql://localhost/test',
        owner=user,
    )


@pytest.fixture
def export_config(db, user, project, account, database):
    return ExportConfig.objects.create(
        name='Test Export Config',
        project=project,
        account=account,
        database=database,
        created_by=user,
    )


@pytest.fixture
def multi_export_config(db, user, account, database):
    config = MultiProjectExportConfig.objects.create(
        name='Multi Export Config',
        account=account,
        database=database,
        created_by=user,
    )
    return config


@pytest.fixture
def export_run(db, export_config):
    return ExportRun.objects.create(
        base_export_config=export_config,
        status=ExportRun.COMPLETED,
    )


@pytest.fixture
def multi_export_run(db, multi_export_config):
    return MultiProjectExportRun.objects.create(
        base_export_config=multi_export_config,
        status=MultiProjectExportRun.COMPLETED,
    )


class TestExportConfigBaseProperties:
    def test_export_config_edit_url(self, export_config):
        expected = reverse(
            'exports:edit_export_config', args=[export_config.id]
        )
        assert export_config.edit_url == expected

    def test_multi_export_config_edit_url(self, multi_export_config):
        expected = reverse(
            'exports:edit_multi_export_config', args=[multi_export_config.id]
        )
        assert multi_export_config.edit_url == expected

    def test_last_run_log_url_none_when_no_run(self, export_config):
        assert export_config.last_run_log_url is None

    def test_last_run_log_url_none_when_no_run_multi(
        self, multi_export_config
    ):
        assert multi_export_config.last_run_log_url is None


class TestExportsHomeView:
    def test_stats_in_context(self, client, db):
        url = reverse('exports:home')
        response = client.get(url)
        assert response.status_code == 200
        assert 'export_stats' in response.context
        assert 'refresh_stats' in response.context
        assert 'forwarding_stats' in response.context

    def test_export_appears_in_list(self, client, export_config):
        url = reverse('exports:home')
        response = client.get(url)
        assert response.status_code == 200
        assert export_config.name in response.content.decode()


class TestConfigTableView:
    def test_requires_login(self, client, user):
        client.logout()
        url = reverse('exports:config_table')
        response = client.get(url)
        assert response.status_code == 302

    def test_returns_200(self, client, db):
        url = reverse('exports:config_table')
        response = client.get(url)
        assert response.status_code == 200

    def test_config_appears(self, client, export_config):
        url = reverse('exports:config_table')
        response = client.get(url)
        assert export_config.name in response.content.decode()

    def test_pagination_default_page_size_10(
        self, client, user, project, account, database
    ):
        for i in range(15):
            ExportConfig.objects.create(
                name=f'Config {i}',
                project=project,
                account=account,
                database=database,
                created_by=user,
            )
        response = client.get(reverse('exports:config_table'))
        assert response.status_code == 200
        content = response.content.decode()
        # Only 10 of the 15 configs should appear
        shown = content.count('Config ')
        assert shown == 10

    def test_page_size_param_respected(
        self, client, user, project, account, database
    ):
        for i in range(25):
            ExportConfig.objects.create(
                name=f'Config {i}',
                project=project,
                account=account,
                database=database,
                created_by=user,
            )
        response = client.get(
            reverse('exports:config_table'), {'page_size': 20}
        )
        assert response.status_code == 200
        shown = response.content.decode().count('Config ')
        assert shown == 20

    def test_etag_match_returns_no_swap(self, client, export_config):
        # First request — get a valid etag
        response = client.get(reverse('exports:config_table'))
        assert response.status_code == 200
        content = response.content.decode()
        # Extract etag from data-etag attribute
        import re

        match = re.search(r'data-etag="([a-f0-9]+)"', content)
        assert match, 'data-etag not found in response'
        etag = match.group(1)

        # Second request with matching etag — should return HX-Reswap: none
        response2 = client.get(reverse('exports:config_table'), {'etag': etag})
        assert response2.status_code == 200
        assert response2.get('HX-Reswap') == 'none'

    def test_etag_mismatch_returns_full_content(self, client, export_config):
        response = client.get(
            reverse('exports:config_table'), {'etag': 'stale'}
        )
        assert response.status_code == 200
        assert response.get('HX-Reswap') is None
        assert export_config.name in response.content.decode()

    def test_page_clamped_when_out_of_range(self, client, export_config):
        response = client.get(reverse('exports:config_table'), {'page': 999})
        assert response.status_code == 200


class TestRunLogView:
    def test_requires_login(self, client, user, export_run):
        client.logout()
        response = client.get(reverse('exports:run_log', args=[export_run.id]))
        assert response.status_code == 302

    def test_returns_log_content(self, client, export_run):
        export_run.log = 'Test log output'
        export_run.save()
        response = client.get(reverse('exports:run_log', args=[export_run.id]))
        assert response.status_code == 200
        assert 'Test log output' in response.content.decode()

    def test_404_for_invalid_run(self, client):
        response = client.get(reverse('exports:run_log', args=[9999]))
        assert response.status_code == 404


class TestMultiRunLogView:
    def test_requires_login(self, client, user, multi_export_run):
        client.logout()
        response = client.get(reverse('exports:multi_run_log', args=[multi_export_run.id]))
        assert response.status_code == 302

    def test_returns_log_content(self, client, multi_export_run):
        multi_export_run.log = 'Multi log output'
        multi_export_run.save()
        response = client.get(
            reverse('exports:multi_run_log', args=[multi_export_run.id])
        )
        assert response.status_code == 200
        assert 'Multi log output' in response.content.decode()
