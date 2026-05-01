import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import override_settings

from apps.commcare.models import (
    CommCareAccount,
    CommCareProject,
    CommCareServer,
)
from apps.db.models import Database
from apps.exports.models import ExportConfig

User = get_user_model()


class TestCommCareAccountAPIKey:
    def setup_method(self):
        User = get_user_model()
        user = User(
            username='testuser',
            email='test@example.com',
            password='testpass',
        )
        server = CommCareServer(
            name='Test Server',
            url='https://test.commcarehq.org',
        )
        self.account = CommCareAccount(
            server=server,
            username='test@example.com',
            owner=user,
        )

    def test_api_key_encryption_and_decryption(self):
        test_api_key = 'my-secret-api-key-12345'
        self.account.api_key = test_api_key
        assert self.account.api_key_encrypted
        assert self.account.api_key_encrypted != test_api_key
        assert self.account.api_key == test_api_key

    def test_api_key_empty(self):
        self.account.api_key = ''
        assert self.account.api_key_encrypted == ''
        assert self.account.api_key == ''

    def test_api_key_none(self):
        self.account.api_key = None
        assert self.account.api_key_encrypted == ''
        assert self.account.api_key == ''

    def test_key_rotation_decryption_from_old_key(self):
        test_api_key = 'my-secret-api-key-12345'

        old_key = Fernet.generate_key()
        with override_settings(FERNET_KEYS=[old_key]):
            self.account.api_key = test_api_key

        current_key = Fernet.generate_key()
        with override_settings(
            FERNET_KEYS=[
                current_key,
                old_key,
            ]
        ):
            assert self.account.api_key == test_api_key

    def test_encryption_uses_current_key(self):
        test_api_key = 'my-secret-api-key-12345'

        current_key = Fernet.generate_key()
        old_key = Fernet.generate_key()
        with override_settings(
            FERNET_KEYS=[
                current_key,
                old_key,
            ]
        ):
            self.account.api_key = test_api_key

        encrypted_bytes = self.account.api_key_encrypted.encode()
        fernet = Fernet(current_key)
        decrypted_bytes = fernet.decrypt(encrypted_bytes)
        assert decrypted_bytes.decode() == test_api_key


@pytest.fixture
def server(db):
    return CommCareServer.objects.create(
        name='Test Server', url='https://test.commcarehq.org'
    )


@pytest.fixture
def project(server):
    return CommCareProject.objects.create(server=server, domain='test-domain')


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        username='owner', email='owner@example.com', password='testpass'
    )


@pytest.fixture
def account(server, owner):
    a = CommCareAccount(
        server=server, username='test@example.com', owner=owner
    )
    a.api_key = 'dummy-key'
    a.save()
    return a


@pytest.mark.django_db
class TestCommCareProjectIsInUse:
    def test_not_in_use_when_no_configs(self, project):
        assert project.is_in_use() is False

    def test_in_use_when_exportconfig_exists(self, project, account):
        with override_settings(FERNET_KEYS=[Fernet.generate_key()]):
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
        assert project.is_in_use() is True

    def test_not_in_use_after_config_deleted(self, project, account):
        with override_settings(FERNET_KEYS=[Fernet.generate_key()]):
            db_obj = Database(name='Test DB 2')
            db_obj.connection_string = 'postgresql://localhost/testdb2'
            db_obj.save()

        config = ExportConfig(
            name='Test Export 2',
            account=account,
            database=db_obj,
            project=project,
        )
        config.config_file.save('test2.xlsx', ContentFile(b''), save=False)
        config.save()
        config.delete()
        assert project.is_in_use() is False


@pytest.mark.django_db
class TestCommCareAccountIsInUse:
    def test_not_in_use_when_no_configs(self, account):
        assert account.is_in_use() is False

    def test_in_use_when_exportconfig_exists(self, project, account):
        with override_settings(FERNET_KEYS=[Fernet.generate_key()]):
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
        assert account.is_in_use() is True
