from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
from apps.db.models import Database
from apps.exports.models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)

User = get_user_model()


@fixture
@use('db')
def user():
    yield User.objects.create_user(
        username='listviewuser', email='lv@example.com', password='pass'
    )


@fixture
def authed_client():
    client = Client()
    client.force_login(user())
    yield client


@fixture
@use('db')
def server():
    server, _ = CommCareServer.objects.get_or_create(url='https://www.commcarehq.org')
    yield server


@fixture
def project():
    yield CommCareProject.objects.create(server=server(), domain='test-domain')


@fixture
def account():
    yield CommCareAccount.objects.create(
        server=server(), username='u@example.com', api_key='key', owner=user()
    )


@fixture
@use('db')
def database():
    yield Database.objects.create(
        name='TestDB',
        connection_string='postgresql://localhost/test',
    )


@fixture
def export_config():
    yield ExportConfig.objects.create(
        name='Test Export Config',
        project=project(),
        account=account(),
        database=database(),
    )


@fixture
def multi_export_config():
    yield MultiProjectExportConfig.objects.create(
        name='Multi Export Config',
        account=account(),
        database=database(),
    )


@fixture
def export_run():
    yield ExportRun.objects.create(
        base_export_config=export_config(),
        status=ExportRun.Status.COMPLETED,
    )


@fixture
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
        expected = reverse('exports:edit_multi_export_config', args=[config.id])
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
