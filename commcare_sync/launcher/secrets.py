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
    overwritten. The file is created with mode 0600 (owner read/write only)
    atomically at open time — via ``os.O_CREAT | os.O_EXCL`` with the mode
    passed to ``os.open`` — so it is never briefly world/group-readable, and
    a crash mid-write cannot leave a permanently wrong-mode file behind (the
    exclusive create also means a concurrent bootstrap loses the race
    cleanly instead of truncating the winner's file).
    """
    secrets_path = data_dir / SECRETS_FILENAME

    secrets = {
        'SECRET_KEY': get_random_secret_key(),
        'FERNET_KEYS': [Fernet.generate_key().decode()],
    }

    try:
        fd = os.open(
            secrets_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, _FILE_MODE
        )
    except FileExistsError:
        return

    with os.fdopen(fd, 'w') as f:
        f.write(json.dumps(secrets, indent=2) + '\n')


def load_secrets(data_dir: Path) -> dict:
    """Load the secrets previously written by :func:`bootstrap_secrets`."""
    secrets_path = data_dir / SECRETS_FILENAME
    return json.loads(secrets_path.read_text())
