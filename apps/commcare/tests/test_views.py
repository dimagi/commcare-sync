import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse

from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer

User = get_user_model()

FERNET_KEY = Fernet.generate_key()


@pytest.fixture
def server(db):
    return CommCareServer.objects.create(
        name='Test Server', url='https://test.commcarehq.org'
    )


@pytest.fixture
def project(server):
    return CommCareProject.objects.create(server=server, domain='test-domain')


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        username='testuser', email='test@example.com', password='testpass'
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username='otheruser', email='other@example.com', password='testpass'
    )


@pytest.fixture
def regular_client(client, regular_user):
    client.force_login(regular_user)
    return client


@pytest.fixture
@override_settings(FERNET_KEYS=[FERNET_KEY])
def account(server, regular_user):
    a = CommCareAccount(server=server, username='test@example.com', owner=regular_user)
    a.api_key = 'dummy-key'
    a.save()
    return a


class TestProjectsView:
    def test_anonymous_redirects_to_login(self, client):
        url = reverse('commcare:projects')
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_logged_in_user_gets_200(self, regular_client):
        url = reverse('commcare:projects')
        response = regular_client.get(url)
        assert response.status_code == 200


class TestAccountsView:
    def test_anonymous_redirects_to_login(self, client):
        url = reverse('commcare:accounts')
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_logged_in_user_gets_200(self, regular_client):
        url = reverse('commcare:accounts')
        response = regular_client.get(url)
        assert response.status_code == 200


class TestDeleteProjectView:
    def test_anonymous_redirects_to_login(self, client, project):
        url = reverse('commcare:delete_project', args=[project.id])
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_get_shows_confirmation(self, regular_client, project):
        url = reverse('commcare:delete_project', args=[project.id])
        response = regular_client.get(url)
        assert response.status_code == 200

    def test_post_deletes_and_redirects(self, regular_client, project):
        project_id = project.id
        url = reverse('commcare:delete_project', args=[project_id])
        response = regular_client.post(url)
        assert response.status_code == 302
        assert reverse('commcare:projects') in response.url
        assert not CommCareProject.objects.filter(id=project_id).exists()

    def test_in_use_get_redirects_to_list(self, regular_client, project, account, db):
        from apps.db.models import Database
        from apps.exports.models import ExportConfig

        with override_settings(FERNET_KEYS=[FERNET_KEY]):
            db_obj = Database(name='Test DB')
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

        url = reverse('commcare:delete_project', args=[project.id])
        response = regular_client.get(url)
        assert response.status_code == 302
        assert reverse('commcare:projects') in response.url

    def test_in_use_post_does_not_delete(self, regular_client, project, account, db):
        from apps.db.models import Database
        from apps.exports.models import ExportConfig

        with override_settings(FERNET_KEYS=[FERNET_KEY]):
            db_obj = Database(name='Test DB 3')
            db_obj.connection_string = 'postgresql://localhost/testdb3'
            db_obj.save()
            config = ExportConfig(
                name='Test Export 3',
                account=account,
                database=db_obj,
                project=project,
            )
            config.config_file.save('test3.xlsx', ContentFile(b''), save=False)
            config.save()

        url = reverse('commcare:delete_project', args=[project.id])
        response = regular_client.post(url)
        assert response.status_code == 302
        assert CommCareProject.objects.filter(id=project.id).exists()


class TestDeleteAccountView:
    def test_anonymous_redirects_to_login(self, client, account):
        url = reverse('commcare:delete_account', args=[account.id])
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_owner_get_shows_confirmation(self, regular_client, account):
        url = reverse('commcare:delete_account', args=[account.id])
        response = regular_client.get(url)
        assert response.status_code == 200

    def test_non_owner_get_returns_403(self, client, other_user, account):
        client.force_login(other_user)
        url = reverse('commcare:delete_account', args=[account.id])
        response = client.get(url)
        assert response.status_code == 403

    def test_owner_post_deletes_and_redirects(self, regular_client, account):
        account_id = account.id
        url = reverse('commcare:delete_account', args=[account_id])
        response = regular_client.post(url)
        assert response.status_code == 302
        assert reverse('commcare:accounts') in response.url
        assert not CommCareAccount.objects.filter(id=account_id).exists()

    def test_in_use_get_redirects_to_list(self, regular_client, account, db):
        from apps.db.models import Database
        from apps.exports.models import ExportConfig

        with override_settings(FERNET_KEYS=[FERNET_KEY]):
            db_obj = Database(name='Account In Use DB')
            db_obj.connection_string = 'postgresql://localhost/testdb'
            db_obj.save()
            config = ExportConfig(
                name='Account Test Export',
                account=account,
                database=db_obj,
                project=CommCareProject.objects.create(
                    server=account.server, domain='guard-test-domain'
                ),
            )
            config.config_file.save('test.xlsx', ContentFile(b''), save=False)
            config.save()

        url = reverse('commcare:delete_account', args=[account.id])
        response = regular_client.get(url)
        assert response.status_code == 302
        assert reverse('commcare:accounts') in response.url

    def test_in_use_post_does_not_delete(self, regular_client, account, db):
        from apps.db.models import Database
        from apps.exports.models import ExportConfig

        with override_settings(FERNET_KEYS=[FERNET_KEY]):
            db_obj = Database(name='Account In Use DB 2')
            db_obj.connection_string = 'postgresql://localhost/testdb2'
            db_obj.save()
            config = ExportConfig(
                name='Account Test Export 2',
                account=account,
                database=db_obj,
                project=CommCareProject.objects.create(
                    server=account.server, domain='guard-test-domain-2'
                ),
            )
            config.config_file.save('test2.xlsx', ContentFile(b''), save=False)
            config.save()

        url = reverse('commcare:delete_account', args=[account.id])
        response = regular_client.post(url)
        assert response.status_code == 302
        assert CommCareAccount.objects.filter(id=account.id).exists()


class TestCreateProjectRedirect:
    def test_success_redirects_to_projects(self, regular_client, server):
        url = reverse('commcare:create_project')
        response = regular_client.post(url, {
            'server': server.id,
            'domain': 'new-domain',
        })
        assert response.status_code == 302
        assert reverse('commcare:projects') in response.url


class TestEditProjectRedirect:
    def test_success_redirects_to_projects(self, regular_client, project, server):
        url = reverse('commcare:edit_project', args=[project.id])
        response = regular_client.post(url, {
            'server': server.id,
            'domain': 'renamed-domain',
        })
        assert response.status_code == 302
        assert reverse('commcare:projects') in response.url


class TestCreateAccountRedirect:
    def test_success_redirects_to_accounts(self, regular_client, server):
        url = reverse('commcare:create_account')
        with override_settings(FERNET_KEYS=[FERNET_KEY]):
            response = regular_client.post(url, {
                'server': server.id,
                'username': 'newaccount@example.com',
                'api_key': 'some-api-key',
            })
        assert response.status_code == 302
        assert reverse('commcare:accounts') in response.url


class TestEditAccountRedirect:
    def test_success_redirects_to_accounts(self, regular_client, account, server):
        url = reverse('commcare:edit_account', args=[account.id])
        with override_settings(FERNET_KEYS=[FERNET_KEY]):
            response = regular_client.post(url, {
                'server': server.id,
                'username': 'updated@example.com',
                'api_key': 'updated-api-key',
            })
        assert response.status_code == 302
        assert reverse('commcare:accounts') in response.url
