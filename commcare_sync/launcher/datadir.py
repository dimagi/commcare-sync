"""Resolution of the commcare-sync data directory.

This module is intentionally free of Django imports: it must be importable
(and callable) before ``django.setup()`` runs, since the resolved directory
feeds into Django settings.
"""

import os
from pathlib import Path

from platformdirs import user_data_dir

DATA_DIR_ENV_VAR = 'COMMCARE_SYNC_DATA_DIR'


def resolve_data_dir(cli_value: str | os.PathLike | None = None) -> Path:
    """Resolve the commcare-sync data directory.

    Precedence, highest first:

    1. ``cli_value`` (e.g. a ``--data-dir`` CLI flag)
    2. The ``COMMCARE_SYNC_DATA_DIR`` environment variable
    3. ``platformdirs.user_data_dir('commcare-sync')``

    The resolved directory (and its ``logs/`` and ``media/`` subdirectories)
    is created if it doesn't already exist. The resolved absolute path is
    also written back to the ``COMMCARE_SYNC_DATA_DIR`` environment variable
    so that Django settings and any subprocesses see one authoritative value.
    """
    if cli_value is not None:
        chosen = cli_value
    elif DATA_DIR_ENV_VAR in os.environ:
        chosen = os.environ[DATA_DIR_ENV_VAR]
    else:
        chosen = user_data_dir('commcare-sync')

    data_dir = Path(chosen).expanduser().resolve()

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / 'logs').mkdir(parents=True, exist_ok=True)
    (data_dir / 'media').mkdir(parents=True, exist_ok=True)

    os.environ[DATA_DIR_ENV_VAR] = str(data_dir)

    return data_dir
