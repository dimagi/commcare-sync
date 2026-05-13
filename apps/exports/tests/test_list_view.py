from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
from apps.db.models import Database
from apps.exports.models import ExportConfig

User = get_user_model()


@fixture
@use('db')
def user():
    yield User.objects.create_user(
        username='listviewuser', email='lv@example.com', password='pass'
    )


@fixture
@use('db')
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
@use('db')
def project():
    yield CommCareProject.objects.create(server=server(), domain='test-domain')


@fixture
@use('db')
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
@use('db')
def export_config():
    yield ExportConfig.objects.create(
        name='Test Export Config',
        project=project(),
        account=account(),
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
