import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from ..models import Database

User = get_user_model()


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        username='dbviewuser', email='dbview@example.com', password='pass'
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username='dbadminuser',
        email='dbadmin@example.com',
        password='pass',
        is_active=True,
        is_superuser=True,
        is_staff=True,
    )


@pytest.fixture
def regular_client(client, regular_user):
    client.force_login(regular_user)
    return client


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def database(db):
    db_obj = Database(name='Test DB')
    db_obj.connection_string = 'postgresql://localhost/testdb'
    db_obj.save()
    return db_obj


class TestCreateDatabaseView:
    def test_anonymous_redirects_to_login(self, client):
        url = reverse('db:create_database')
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_regular_user_gets_403(self, regular_client):
        url = reverse('db:create_database')
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_admin_get_returns_200(self, admin_client):
        url = reverse('db:create_database')
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_admin_post_redirects_on_success(self, admin_client):
        url = reverse('db:create_database')
        response = admin_client.post(
            url,
            {
                'name': 'New Test DB',
                'connection_string': 'postgresql://localhost/newdb',
            },
        )
        assert response.status_code == 302
        assert reverse('db:databases') in response.url


class TestEditDatabaseView:
    def test_anonymous_redirects_to_login(self, client, database):
        url = reverse('db:edit_database', args=[database.id])
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_regular_user_gets_403(self, regular_client, database):
        url = reverse('db:edit_database', args=[database.id])
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_admin_get_returns_200(self, admin_client, database):
        url = reverse('db:edit_database', args=[database.id])
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_admin_post_redirects_on_success(self, admin_client, database):
        url = reverse('db:edit_database', args=[database.id])
        response = admin_client.post(
            url, {'name': 'Renamed DB', 'connection_string': ''}
        )
        assert response.status_code == 302
        assert reverse('db:databases') in response.url


class TestDeleteDatabaseView:
    def test_anonymous_redirects_to_login(self, client, database):
        url = reverse('db:delete_database', args=[database.id])
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_regular_user_gets_403(self, regular_client, database):
        url = reverse('db:delete_database', args=[database.id])
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_admin_get_returns_200(self, admin_client, database):
        url = reverse('db:delete_database', args=[database.id])
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_admin_post_redirects_on_success(self, admin_client, database):
        url = reverse('db:delete_database', args=[database.id])
        response = admin_client.post(url)
        assert response.status_code == 302
        assert reverse('db:databases') in response.url


class TestDeleteDatabaseViewInUseGuard:
    @pytest.fixture
    def database_in_use(self, admin_user, db):
        from cryptography.fernet import Fernet
        from django.test import override_settings

        from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
        from apps.db.models import Database
        from apps.exports.models import ExportConfig

        with override_settings(FERNET_KEYS=[Fernet.generate_key()]):
            server = CommCareServer.objects.create(
                name='Test', url='https://test.commcarehq.org'
            )
            project = CommCareProject.objects.create(server=server, domain='test')
            account = CommCareAccount(
                server=server, username='test@example.com', owner=admin_user
            )
            account.api_key = 'dummy'
            account.save()

            db_obj = Database(name='In Use DB')
            db_obj.connection_string = 'postgresql://localhost/testdb'
            db_obj.save()

            from django.core.files.base import ContentFile
            config = ExportConfig(
                name='Test Export',
                account=account,
                database=db_obj,
                project=project,
            )
            config.config_file.save('test.xlsx', ContentFile(b''), save=False)
            config.save()

        return db_obj

    def test_post_on_in_use_database_redirects_with_error(
        self, admin_client, database_in_use
    ):
        from django.urls import reverse
        url = reverse('db:delete_database', args=[database_in_use.id])
        response = admin_client.post(url)
        assert response.status_code == 302
        assert reverse('db:databases') in response.url
        # Database must still exist
        from apps.db.models import Database
        assert Database.objects.filter(id=database_in_use.id).exists()

    def test_get_on_in_use_database_redirects_with_error(
        self, admin_client, database_in_use
    ):
        from django.urls import reverse
        url = reverse('db:delete_database', args=[database_in_use.id])
        response = admin_client.get(url)
        assert response.status_code == 302
        assert reverse('db:databases') in response.url
