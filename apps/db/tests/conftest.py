import pytest
from cryptography.fernet import Fernet
from django.conf import settings


@pytest.fixture(scope='session', autouse=True)
def set_fernet_keys():
    """Ensure FERNET_KEYS is set for tests."""
    if not hasattr(settings, 'FERNET_KEYS') or not settings.FERNET_KEYS:
        settings.FERNET_KEYS = [Fernet.generate_key()]
