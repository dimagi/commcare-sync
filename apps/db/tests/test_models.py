import doctest

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import override_settings
from unmagic import fixture, use

from apps.db.models import Database

User = get_user_model()


class TestDatabaseConnectionString:

    def setup_method(self):
        self.db = Database(
            name='Test Database',
        )

    def test_connection_string_encryption_and_decryption(self):
        test_connection_string = 'postgresql://user:password@localhost:5432/dbname'
        self.db.connection_string = test_connection_string
        assert self.db.connection_string_encrypted
        assert self.db.connection_string_encrypted != test_connection_string
        assert self.db.connection_string == test_connection_string

    def test_connection_string_empty(self):
        self.db.connection_string = ''
        assert self.db.connection_string_encrypted == ''
        assert self.db.connection_string == ''

    def test_connection_string_none(self):
        self.db.connection_string = None
        assert self.db.connection_string_encrypted == ''
        assert self.db.connection_string == ''

    def test_key_rotation_decryption_from_old_key(self):
        test_connection_string = 'postgresql://user:password@localhost:5432/dbname'

        old_key = Fernet.generate_key()
        with override_settings(FERNET_KEYS=[old_key]):
            self.db.connection_string = test_connection_string

        current_key = Fernet.generate_key()
        with override_settings(FERNET_KEYS=[
            current_key,
            old_key,
        ]):
            assert self.db.connection_string == test_connection_string

    def test_encryption_uses_current_key(self):
        test_connection_string = 'postgresql://user:password@localhost:5432/dbname'

        current_key = Fernet.generate_key()
        old_key = Fernet.generate_key()
        with override_settings(FERNET_KEYS=[
            current_key,
            old_key,
        ]):
            self.db.connection_string = test_connection_string

        encrypted_bytes = self.db.connection_string_encrypted.encode()
        fernet = Fernet(current_key)
        decrypted_bytes = fernet.decrypt(encrypted_bytes)
        assert decrypted_bytes.decode() == test_connection_string


def test_doctests():
    import apps.exports.models as module

    results = doctest.testmod(module)
    assert results.failed == 0


@fixture
@use('db')
def database_for_is_in_use():
    """A persisted Database for is_in_use tests (avoids hitting FERNET_KEYS)."""
    db_obj = Database(name='Test DB IsInUse')
    db_obj.connection_string = 'postgresql://localhost/testdb'
    db_obj.save()
    yield db_obj


@use('db')
class TestDatabaseIsInUse:
    @use(database_for_is_in_use)
    def test_not_in_use_when_no_configs(self):
        assert database_for_is_in_use().is_in_use() is False

    @use(database_for_is_in_use)
    def test_is_in_use_when_export_config_exists(self):
        from django.core.files.base import ContentFile

        from apps.commcare.models import (
            CommCareAccount,
            CommCareProject,
            CommCareServer,
        )
        from apps.exports.models import ExportConfig

        db_obj = database_for_is_in_use()
        server = CommCareServer.objects.create(
            name='Test Server', url='https://test.commcarehq.org'
        )
        project = CommCareProject.objects.create(
            server=server, domain='test-domain'
        )
        owner = User.objects.create_user(
            email='dbisinuse@example.com',
            password='testpass',
        )
        account = CommCareAccount(
            server=server, username='test@example.com', owner=owner
        )
        account.api_key = 'dummy-key'
        account.save()

        config = ExportConfig(
            name='Test Export',
            account=account,
            database=db_obj,
            project=project,
        )
        config.config_file.save('test.xlsx', ContentFile(b''), save=False)
        config.save()
        assert db_obj.is_in_use() is True
