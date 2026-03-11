import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
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
    server, _ = CommCareServer.objects.get_or_create(url='https://www.commcarehq.org')
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
        expected = reverse('exports:edit_export_config', args=[export_config.id])
        assert export_config.edit_url == expected

    def test_multi_export_config_edit_url(self, multi_export_config):
        expected = reverse('exports:edit_multi_export_config', args=[multi_export_config.id])
        assert multi_export_config.edit_url == expected

    def test_last_run_log_url_none_when_no_run(self, export_config):
        assert export_config.last_run_log_url is None

    def test_last_run_log_url_none_when_no_run_multi(self, multi_export_config):
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
