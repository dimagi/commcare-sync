from urllib.parse import urlsplit

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.db import models

from apps.commcare.models import BaseModel


class Database(BaseModel):
    name = models.CharField(max_length=100)
    connection_string_encrypted = models.CharField(max_length=1000)

    def __str__(self):
        return self.name

    @property
    def connection_string(self):
        """Decrypt and return the connection string."""
        if not self.connection_string_encrypted:
            return ''

        fernet_keys = (  # Include rotated keys for decryption
            key.encode() if isinstance(key, str) else key
            for key in settings.FERNET_KEYS
        )
        fernet = MultiFernet([Fernet(k) for k in fernet_keys])
        encrypted_bytes = self.connection_string_encrypted.encode()
        decrypted_bytes = fernet.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()

    @connection_string.setter
    def connection_string(self, value):
        """Encrypt and store the connection string."""
        if not value:
            self.connection_string_encrypted = ''
            return

        key = settings.FERNET_KEYS[0]  # Encrypt using the current key
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        encrypted_bytes = fernet.encrypt(value.encode())
        self.connection_string_encrypted = encrypted_bytes.decode()

    @property
    def dialect(self):
        """
        Returns the SQLAlchemy dialect of the database URL.

        >>> db = Database(name='example')
        >>> db.connection_string = 'mysql+pymysql://user:pwd@localhost/db'
        >>> db.dialect
        'mysql'

        """
        scheme = urlsplit(self.connection_string).scheme
        return scheme.split('+')[0] if '+' in scheme else scheme
