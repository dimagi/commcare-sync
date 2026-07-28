"""First-run secrets bootstrap for the commcare-sync launcher.

This module is intentionally free of Django imports (aside from the
management utility used to generate a secret key, which is safe to import
without configured settings): it must be importable and callable before
``django.setup()`` runs, since the settings module reads the secrets it
writes.
"""

import json
import os
import stat
from pathlib import Path

from cryptography.fernet import Fernet
from django.core.management.utils import get_random_secret_key

SECRETS_FILENAME = 'secrets.json'

_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0600


def bootstrap_secrets(data_dir: Path) -> None:
    """Create ``<data_dir>/secrets.json`` on first run.

    Does nothing if the file already exists, so existing secrets are never
    overwritten. The file is written with mode 0600 (owner read/write only).
    """
    secrets_path = data_dir / SECRETS_FILENAME
    if secrets_path.exists():
        return

    secrets = {
        'SECRET_KEY': get_random_secret_key(),
        'FERNET_KEYS': [Fernet.generate_key().decode()],
    }

    secrets_path.write_text(json.dumps(secrets, indent=2) + '\n')
    os.chmod(secrets_path, _FILE_MODE)


def load_secrets(data_dir: Path) -> dict:
    """Load the secrets previously written by :func:`bootstrap_secrets`."""
    secrets_path = data_dir / SECRETS_FILENAME
    return json.loads(secrets_path.read_text())
