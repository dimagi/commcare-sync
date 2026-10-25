"""
First-run secrets for the launcher.

Runs before ``django.setup()``: the settings module reads the file this
writes.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

SECRETS_FILENAME = 'secrets.json'
TEMP_PREFIX = '.secrets-'
SECRET_NAMES = ('SECRET_KEY', 'FERNET_KEYS')

logger = logging.getLogger(__name__)


def bootstrap_secrets(data_dir: Path) -> None:
    """
    Create ``secrets.json`` once. Existing secrets are never rewritten:
    that would invalidate sessions and every Fernet-encrypted password.
    """
    path = data_dir / SECRETS_FILENAME
    for leftover in data_dir.glob(TEMP_PREFIX + '*'):
        leftover.unlink()  # from a crash between writing and linking
    if path.exists():
        return
    keys = {
        'SECRET_KEY': get_random_secret_key(),
        'FERNET_KEYS': [Fernet.generate_key().decode()],
    }
    # Written in full under a temporary name, then linked into place, so
    # that the file is never briefly readable by others, never partially
    # written, and never replaces one that another process created first.
    # ``mkstemp`` opens with mode 0600. On Windows the mode means nothing
    # and the file inherits the data directory's ACL, which is under the
    # user's profile.
    fd, temp_name = tempfile.mkstemp(dir=data_dir, prefix=TEMP_PREFIX)
    temp_path = Path(temp_name)
    try:
        _write_keys(fd, keys)
        _link_into_place(temp_path, path, keys)
    finally:
        temp_path.unlink(missing_ok=True)


def _link_into_place(temp_path: Path, path: Path, keys: dict) -> None:
    try:
        os.link(temp_path, path)
    except FileExistsError:
        return  # another process got there first
    except OSError as err:
        # A filesystem without hard links. Written in place, the file
        # could be left partial by a crash, but it still never replaces
        # one that another process created first.
        logger.info(
            'Cannot link %s into place (%s); writing it in place',
            path.name,
            err,
        )
        _write_exclusively(path, keys)


def _write_exclusively(path: Path, keys: dict) -> None:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    _write_keys(fd, keys)


def _write_keys(fd: int, keys: dict) -> None:
    with os.fdopen(fd, 'w') as file:
        json.dump(keys, file, indent=2)


def load_secrets(data_dir: Path) -> dict:
    path = data_dir / SECRETS_FILENAME
    try:
        stored = json.loads(path.read_text())
        return {name: stored[name] for name in SECRET_NAMES}
    except FileNotFoundError:
        raise ImproperlyConfigured(
            f'{path} does not exist. The launcher creates it on first run.'
        ) from None
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise ImproperlyConfigured(
            f'Cannot read {path} ({err!r}). Restore it from a backup; '
            'without its keys, stored passwords cannot be decrypted. '
            'Deleting it starts over with fresh keys.'
        ) from err
