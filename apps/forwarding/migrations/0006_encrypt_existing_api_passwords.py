from cryptography.fernet import Fernet
from django.conf import settings
from django.db import migrations


def encrypt_api_passwords(apps, schema_editor):
    """Encrypt existing plaintext API passwords."""
    ForwardingDestination = apps.get_model('forwarding', 'ForwardingDestination')

    fernet_key = settings.FERNET_KEYS[0]
    cipher = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)

    for destination in ForwardingDestination.objects.all():
        if destination.api_password_encrypted:
            plaintext = destination.api_password_encrypted
            encrypted = cipher.encrypt(plaintext.encode())
            destination.api_password_encrypted = encrypted.decode()
            destination.save(update_fields=['api_password_encrypted'])


def decrypt_api_passwords(apps, schema_editor):
    """Decrypt API passwords back to plaintext (for rollback)."""
    ForwardingDestination = apps.get_model('forwarding', 'ForwardingDestination')

    fernet_key = settings.FERNET_KEYS[0]
    cipher = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)

    for destination in ForwardingDestination.objects.all():
        if destination.api_password_encrypted:
            encrypted = destination.api_password_encrypted
            decrypted = cipher.decrypt(encrypted.encode())
            destination.api_password_encrypted = decrypted.decode()
            destination.save(update_fields=['api_password_encrypted'])


class Migration(migrations.Migration):

    dependencies = [
        ('forwarding', '0005_rename_and_resize_api_password'),
    ]

    operations = [
        migrations.RunPython(encrypt_api_passwords, decrypt_api_passwords),
    ]
