from cryptography.fernet import Fernet
from django.core.files.base import ContentFile
from django.test import Client, override_settings
from django.urls import reverse
from unmagic import fixture, use

from apps.commcare.models import CommCareProject
from apps.db.models import Database
from apps.exports.models import ExportConfig
from tests.fixtures import (
    commcare_account,
    commcare_project,
    commcare_server,
    user,
)

FERNET_KEY = Fernet.generate_key()


@fixture
@use(user)
def regular_client():
    client = Client()
    client.force_login(user())
    yield client


class TestProjectsView:
    def test_anonymous_redirects_to_login(self):
        url = reverse('commcare:projects')
        response = Client().get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    @use(regular_client)
    def test_logged_in_user_gets_200(self):
        url = reverse('commcare:projects')
        response = regular_client().get(url)
        assert response.status_code == 200


class TestAccountsView:
    def test_anonymous_redirects_to_login(self):
        url = reverse('commcare:accounts')
        response = Client().get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    @use(regular_client)
    def test_logged_in_user_gets_200(self):
        url = reverse('commcare:accounts')
        response = regular_client().get(url)
        assert response.status_code == 200


@use(regular_client, commcare_server)
def test_create_project_redirect():
    url = reverse('commcare:create_project')
    response = regular_client().post(url, {
        'server': commcare_server().id,
        'domain': 'new-domain',
    })
    assert response.status_code == 302
    assert reverse('commcare:projects') in response.url


@use(regular_client, commcare_server, commcare_project)
def test_edit_project_redirect():
    url = reverse('commcare:edit_project', args=[commcare_project().id])
    response = regular_client().post(url, {
        'server': commcare_server().id,
        'domain': 'renamed-domain',
    })
    assert response.status_code == 302
    assert reverse('commcare:projects') in response.url


@use(regular_client, commcare_server)
def test_create_account_redirect():
    url = reverse('commcare:create_account')
    with override_settings(FERNET_KEYS=[FERNET_KEY]):
        response = regular_client().post(url, {
            'server': commcare_server().id,
            'username': 'newaccount@example.com',
            'api_key': 'some-api-key',
        })
    assert response.status_code == 302
    assert reverse('commcare:accounts') in response.url


@use(regular_client, commcare_account, commcare_server)
def test_edit_account_redirect():
    url = reverse('commcare:edit_account', args=[commcare_account().id])
    with override_settings(FERNET_KEYS=[FERNET_KEY]):
        response = regular_client().post(url, {
            'server': commcare_server().id,
            'username': 'updated@example.com',
            'api_key': 'updated-api-key',
        })
    assert response.status_code == 302
    assert reverse('commcare:accounts') in response.url


@use(regular_client, commcare_project, commcare_account)
class TestDeleteProjectView:
    def test_anonymous_redirects_to_login(self):
        url = reverse('commcare:delete_project', args=[commcare_project().id])
        response = Client().get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_get_shows_confirmation(self):
        url = reverse('commcare:delete_project', args=[commcare_project().id])
        response = regular_client().get(url)
        assert response.status_code == 200

    def test_post_deletes_and_redirects(self):
        project_id = commcare_project().id
        url = reverse('commcare:delete_project', args=[project_id])
        response = regular_client().post(url)
        assert response.status_code == 302
        assert reverse('commcare:projects') in response.url
        assert not CommCareProject.objects.filter(id=project_id).exists()

    def test_in_use_get_redirects_to_list(self):
        with override_settings(FERNET_KEYS=[FERNET_KEY]):
            db_obj = Database(name='Test DB')
            db_obj.connection_string = 'postgresql://localhost/testdb'
            db_obj.save()
            config = ExportConfig(
                name='Test Export',
                account=commcare_account(),
                database=db_obj,
                project=commcare_project(),
            )
            config.config_file.save('test.xlsx', ContentFile(b''), save=False)
            config.save()

        url = reverse('commcare:delete_project', args=[commcare_project().id])
        response = regular_client().get(url)
        assert response.status_code == 302
        assert reverse('commcare:projects') in response.url

    def test_in_use_post_does_not_delete(self):
        with override_settings(FERNET_KEYS=[FERNET_KEY]):
            db_obj = Database(name='Test DB 3')
            db_obj.connection_string = 'postgresql://localhost/testdb3'
            db_obj.save()
            config = ExportConfig(
                name='Test Export 3',
                account=commcare_account(),
                database=db_obj,
                project=commcare_project(),
            )
            config.config_file.save('test3.xlsx', ContentFile(b''), save=False)
            config.save()

        url = reverse('commcare:delete_project', args=[commcare_project().id])
        response = regular_client().post(url)
        assert response.status_code == 302
        assert CommCareProject.objects.filter(id=commcare_project().id).exists()
