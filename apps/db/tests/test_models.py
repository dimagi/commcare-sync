import doctest

from cryptography.fernet import Fernet
from django.test import override_settings

from apps.db.models import Database


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
