from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.db import migrations


def encrypt_connection_strings(apps, schema_editor):
    """Encrypt existing plaintext connection strings."""
    ExportDatabase = apps.get_model('exports', 'ExportDatabase')

    current_key = settings.FERNET_KEYS[0]
    cipher = Fernet(current_key.encode() if isinstance(current_key, str) else current_key)

    for db in ExportDatabase.objects.all():
        if db.connection_string_encrypted:
            plaintext = db.connection_string_encrypted
            encrypted = cipher.encrypt(plaintext.encode())
            db.connection_string_encrypted = encrypted.decode()
            db.save(update_fields=['connection_string_encrypted'])


def decrypt_connection_strings(apps, schema_editor):
    """Decrypt connection strings back to plaintext for rollback."""
    ExportDatabase = apps.get_model('exports', 'ExportDatabase')

    # Include rotated keys for decryption
    fernet_keys = [
        key.encode() if isinstance(key, str) else key
        for key in settings.FERNET_KEYS
    ]
    multi_fernet = MultiFernet([Fernet(k) for k in fernet_keys])

    for db in ExportDatabase.objects.all():
        if db.connection_string_encrypted:
            encrypted = db.connection_string_encrypted
            decrypted = multi_fernet.decrypt(encrypted.encode())
            db.connection_string_encrypted = decrypted.decode()
            db.save(update_fields=['connection_string_encrypted'])


class Migration(migrations.Migration):

    dependencies = [
        ('exports', '0019_rename_connection_string'),
    ]

    operations = [
        migrations.RunPython(
            encrypt_connection_strings,
            decrypt_connection_strings,
        ),
    ]
