from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

from apps.commcare.models import (
    CommCareAccount,
    CommCareProject,
    CommCareServer,
)
from apps.exports.models import ExportConfig

from ..models import Database

User = get_user_model()


@fixture
@use('db')
def regular_user():
    yield User.objects.create_user(
        username='dbviewuser', email='dbview@example.com', password='testpass'
    )


@fixture
@use('db')
def admin_user():
    yield User.objects.create_user(
        username='dbadminuser',
        email='dbadmin@example.com',
        password='testpass',
        is_active=True,
        is_superuser=True,
        is_staff=True,
    )


@fixture
def regular_client():
    client = Client()
    client.force_login(regular_user())
    yield client


@fixture
def admin_client():
    client = Client()
    client.force_login(admin_user())
    yield client


@fixture
@use('db')
def database():
    db_obj = Database(name='Test DB')
    db_obj.connection_string = 'postgresql://localhost/testdb'
    db_obj.save()
    yield db_obj


class TestCreateDatabaseView:
    def test_anonymous_redirects_to_login(self):
        url = reverse('db:create_database')
        response = Client().get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    @use(regular_client)
    def test_regular_user_gets_403(self):
        url = reverse('db:create_database')
        response = regular_client().get(url)
        assert response.status_code == 403

    @use(admin_client)
    def test_admin_get_returns_200(self):
        url = reverse('db:create_database')
        response = admin_client().get(url)
        assert response.status_code == 200

    @use(admin_client)
    def test_admin_post_redirects_on_success(self):
        url = reverse('db:create_database')
        response = admin_client().post(
            url,
            {
                'name': 'New Test DB',
                'connection_string': 'postgresql://localhost/newdb',
            },
        )
        assert response.status_code == 302
        assert reverse('db:databases') in response.url


class TestEditDatabaseView:
    @use(database)
    def test_anonymous_redirects_to_login(self):
        url = reverse('db:edit_database', args=[database().id])
        response = Client().get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    @use(regular_client, database)
    def test_regular_user_gets_403(self):
        url = reverse('db:edit_database', args=[database().id])
        response = regular_client().get(url)
        assert response.status_code == 403

    @use(admin_client, database)
    def test_admin_get_returns_200(self):
        url = reverse('db:edit_database', args=[database().id])
        response = admin_client().get(url)
        assert response.status_code == 200

    @use(admin_client, database)
    def test_admin_post_redirects_on_success(self):
        url = reverse('db:edit_database', args=[database().id])
        response = admin_client().post(
            url, {'name': 'Renamed DB', 'connection_string': ''}
        )
        assert response.status_code == 302
        assert reverse('db:databases') in response.url


class TestDeleteDatabaseView:
    @use(database)
    def test_anonymous_redirects_to_login(self):
        url = reverse('db:delete_database', args=[database().id])
        response = Client().get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    @use(regular_client, database)
    def test_regular_user_gets_403(self):
        url = reverse('db:delete_database', args=[database().id])
        response = regular_client().get(url)
        assert response.status_code == 403

    @use(admin_client, database)
    def test_admin_get_returns_200(self):
        url = reverse('db:delete_database', args=[database().id])
        response = admin_client().get(url)
        assert response.status_code == 200

    @use(admin_client, database)
    def test_admin_post_redirects_on_success(self):
        url = reverse('db:delete_database', args=[database().id])
        response = admin_client().post(url)
        assert response.status_code == 302
        assert reverse('db:databases') in response.url


@fixture
@use('db')
def database_in_use():
    server = CommCareServer.objects.create(
        name='Test', url='https://test.commcarehq.org'
    )
    project = CommCareProject.objects.create(server=server, domain='test')
    account = CommCareAccount(
        server=server, username='test@example.com', owner=admin_user()
    )
    account.api_key = 'dummy'
    account.save()

    db_obj = Database(name='In Use DB')
    db_obj.connection_string = 'postgresql://localhost/testdb'
    db_obj.save()

    config = ExportConfig(
        name='Test Export',
        account=account,
        database=db_obj,
        project=project,
    )
    config.config_file.save('test.xlsx', ContentFile(b''), save=False)
    config.save()

    yield db_obj


class TestDeleteDatabaseViewInUseGuard:
    @use(admin_client, database_in_use)
    def test_post_on_in_use_database_redirects_with_error(self):
        db_obj = database_in_use()
        url = reverse('db:delete_database', args=[db_obj.id])
        response = admin_client().post(url)
        assert response.status_code == 302
        assert reverse('db:databases') in response.url
        # Database must still exist
        assert Database.objects.filter(id=db_obj.id).exists()

    @use(admin_client, database_in_use)
    def test_get_on_in_use_database_redirects_with_error(self):
        db_obj = database_in_use()
        url = reverse('db:delete_database', args=[db_obj.id])
        response = admin_client().get(url)
        assert response.status_code == 302
        assert reverse('db:databases') in response.url
        assert Database.objects.filter(id=db_obj.id).exists()
