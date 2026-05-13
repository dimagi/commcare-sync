from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

from ..models import Database

User = get_user_model()


@fixture
@use('db')
def regular_user():
    yield User.objects.create_user(
        username='dbviewuser', email='dbview@example.com', password='pass'
    )


@fixture
@use('db')
def admin_user():
    yield User.objects.create_user(
        username='dbadminuser',
        email='dbadmin@example.com',
        password='pass',
        is_active=True,
        is_superuser=True,
        is_staff=True,
    )


@fixture
@use('db')
def regular_client():
    client = Client()
    client.force_login(regular_user())
    yield client


@fixture
@use('db')
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


@use(database)
class TestEditDatabaseView:
    def test_anonymous_redirects_to_login(self):
        url = reverse('db:edit_database', args=[database().id])
        response = Client().get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    @use(regular_client)
    def test_regular_user_gets_403(self):
        url = reverse('db:edit_database', args=[database().id])
        response = regular_client().get(url)
        assert response.status_code == 403

    @use(admin_client)
    def test_admin_get_returns_200(self):
        url = reverse('db:edit_database', args=[database().id])
        response = admin_client().get(url)
        assert response.status_code == 200

    @use(admin_client)
    def test_admin_post_redirects_on_success(self):
        url = reverse('db:edit_database', args=[database().id])
        response = admin_client().post(
            url, {'name': 'Renamed DB', 'connection_string': ''}
        )
        assert response.status_code == 302
        assert reverse('db:databases') in response.url


@use(database)
class TestDeleteDatabaseView:
    def test_anonymous_redirects_to_login(self):
        url = reverse('db:delete_database', args=[database().id])
        response = Client().get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    @use(regular_client)
    def test_regular_user_gets_403(self):
        url = reverse('db:delete_database', args=[database().id])
        response = regular_client().get(url)
        assert response.status_code == 403

    @use(admin_client)
    def test_admin_get_returns_200(self):
        url = reverse('db:delete_database', args=[database().id])
        response = admin_client().get(url)
        assert response.status_code == 200

    @use(admin_client)
    def test_admin_post_redirects_on_success(self):
        url = reverse('db:delete_database', args=[database().id])
        response = admin_client().post(url)
        assert response.status_code == 302
        assert reverse('db:databases') in response.url
