from cryptography.fernet import Fernet
from django.conf import settings
from django.db import migrations


def encrypt_api_keys(apps, schema_editor):
    """Encrypt existing plaintext API keys."""
    CommCareAccount = apps.get_model('commcare', 'CommCareAccount')

    fernet_key = settings.FERNET_KEYS[0]  # Current Fernet key
    cipher = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)

    for account in CommCareAccount.objects.all():
        if account.api_key_encrypted:
            plaintext = account.api_key_encrypted
            encrypted = cipher.encrypt(plaintext.encode())
            account.api_key_encrypted = encrypted.decode()
            account.save(update_fields=['api_key_encrypted'])


def decrypt_api_keys(apps, schema_editor):
    """Decrypt API keys back to plaintext (for rollback)."""
    CommCareAccount = apps.get_model('commcare', 'CommCareAccount')

    fernet_key = settings.FERNET_KEYS[0]
    cipher = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)

    for account in CommCareAccount.objects.all():
        if account.api_key_encrypted:
            encrypted = account.api_key_encrypted
            decrypted = cipher.decrypt(encrypted.encode())
            account.api_key_encrypted = decrypted.decode()
            account.save(update_fields=['api_key_encrypted'])


class Migration(migrations.Migration):

    dependencies = [
        ('commcare', '0006_rename_and_encrypt_api_key'),
    ]

    operations = [
        migrations.RunPython(encrypt_api_keys, decrypt_api_keys),
    ]
