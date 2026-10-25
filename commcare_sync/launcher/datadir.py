"""
Resolution of the commcare-sync data directory.

Free of Django imports: it runs before ``django.setup()``, because the
resolved directory feeds into Django settings.
"""

import os
from pathlib import Path

from platformdirs import user_data_dir

from commcare_sync.launcher.env import (
    APP_NAME,
    DATA_DIR_ENV_VAR,
    LOGS_DIRNAME,
    MEDIA_DIRNAME,
)


def resolve_data_dir(cli_value: str | os.PathLike | None = None) -> Path:
    """
    Precedence: ``cli_value``, then ``COMMCARE_SYNC_DATA_DIR``, then the
    platform's per-user data directory.

    Creates the directory and the subdirectories that must exist before
    Django starts.
    """
    if cli_value is not None:
        chosen = cli_value
    elif DATA_DIR_ENV_VAR in os.environ:
        chosen = os.environ[DATA_DIR_ENV_VAR]
    else:
        chosen = user_data_dir(APP_NAME, appauthor=False)
    data_dir = Path(chosen).expanduser().resolve()
    for subdir in (LOGS_DIRNAME, MEDIA_DIRNAME):
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)
    return data_dir
