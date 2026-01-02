from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.commcare.models import CommCareAccount, CommCareServer


class TestCommCareAccountAPIKey:

    def setup_method(self):
        User = get_user_model()
        user = User(
            username='testuser',
            email='test@example.com',
            password='testpass123',
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
        with override_settings(FERNET_KEYS=[
            current_key,
            old_key,
        ]):
            assert self.account.api_key == test_api_key

    def test_encryption_uses_current_key(self):
        test_api_key = 'my-secret-api-key-12345'

        current_key = Fernet.generate_key()
        old_key = Fernet.generate_key()
        with override_settings(FERNET_KEYS=[
            current_key,
            old_key,
        ]):
            self.account.api_key = test_api_key

        encrypted_bytes = self.account.api_key_encrypted.encode()
        fernet = Fernet(current_key)
        decrypted_bytes = fernet.decrypt(encrypted_bytes)
        assert decrypted_bytes.decode() == test_api_key
