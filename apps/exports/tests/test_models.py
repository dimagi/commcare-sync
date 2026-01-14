from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.exports.models import ExportDatabase


class TestExportDatabaseConnectionString:

    def setup_method(self):
        User = get_user_model()
        user = User(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )
        self.export_db = ExportDatabase(
            name='Test Database',
            owner=user,
        )

    def test_connection_string_encryption_and_decryption(self):
        test_connection_string = 'postgresql://user:password@localhost:5432/dbname'
        self.export_db.connection_string = test_connection_string
        assert self.export_db.connection_string_encrypted
        assert self.export_db.connection_string_encrypted != test_connection_string
        assert self.export_db.connection_string == test_connection_string

    def test_connection_string_empty(self):
        self.export_db.connection_string = ''
        assert self.export_db.connection_string_encrypted == ''
        assert self.export_db.connection_string == ''

    def test_connection_string_none(self):
        self.export_db.connection_string = None
        assert self.export_db.connection_string_encrypted == ''
        assert self.export_db.connection_string == ''

    def test_key_rotation_decryption_from_old_key(self):
        test_connection_string = 'postgresql://user:password@localhost:5432/dbname'

        old_key = Fernet.generate_key()
        with override_settings(FERNET_KEYS=[old_key]):
            self.export_db.connection_string = test_connection_string

        current_key = Fernet.generate_key()
        with override_settings(FERNET_KEYS=[
            current_key,
            old_key,
        ]):
            assert self.export_db.connection_string == test_connection_string

    def test_encryption_uses_current_key(self):
        test_connection_string = 'postgresql://user:password@localhost:5432/dbname'

        current_key = Fernet.generate_key()
        old_key = Fernet.generate_key()
        with override_settings(FERNET_KEYS=[
            current_key,
            old_key,
        ]):
            self.export_db.connection_string = test_connection_string

        encrypted_bytes = self.export_db.connection_string_encrypted.encode()
        fernet = Fernet(current_key)
        decrypted_bytes = fernet.decrypt(encrypted_bytes)
        assert decrypted_bytes.decode() == test_connection_string
