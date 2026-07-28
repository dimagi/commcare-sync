"""Launcher-mode settings overlay for commcare-sync.

When ``COMMCARE_SYNC_DATA_DIR`` is set, :mod:`commcare_sync.settings` calls
:func:`apply_launcher_overlay` instead of loading ``settings_local.py``. This
module is the single place that decides what a packaged (desktop/server)
install's settings look like, so the data-dir file is the only override
channel and precedence is explicit rather than depending on import order.
"""

import copy
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from commcare_sync.launcher.secrets import load_secrets

DATA_DIR_SETTINGS_FILENAME = 'settings.py'


def _truthy(value: str) -> bool:
    return value.strip().lower() in ('1', 'true', 'yes')


def apply_launcher_overlay(
    data_dir: Path,
    mode: str | None,
    port: str | None,
    module_globals: dict,
) -> None:
    """Mutate ``module_globals`` (the settings module's globals) for launcher mode.

    ``data_dir`` is assumed to already exist (created by
    :func:`commcare_sync.launcher.datadir.resolve_data_dir`).
    """
    # --- Database, logs, media: relocate into the data dir, preserving the
    # existing sqlite OPTIONS (WAL/busy_timeout/transaction-mode).
    databases = module_globals['DATABASES']
    databases['default']['NAME'] = str(data_dir / 'db.sqlite3')
    module_globals['LOG_DIR'] = str(data_dir / 'logs')
    module_globals['MEDIA_ROOT'] = str(data_dir / 'media')
    # Collected static files go to the data dir too: the code an installed
    # commcare-sync runs from (site-packages, or a frozen bundle) may well be
    # read-only, but the data dir is ours by definition.
    module_globals['STATIC_ROOT'] = str(data_dir / 'static_root')

    # --- Secrets: env vars win, else the data-dir secrets file.
    if 'SECRET_KEY' not in os.environ or 'FERNET_KEYS' not in os.environ:
        secrets = load_secrets(data_dir)
        if 'SECRET_KEY' not in os.environ:
            module_globals['SECRET_KEY'] = secrets['SECRET_KEY']
        if 'FERNET_KEYS' not in os.environ:
            module_globals['FERNET_KEYS'] = secrets['FERNET_KEYS']

    # --- Mode-specific conditionals.
    if mode == 'desktop':
        module_globals['DEBUG'] = False
        module_globals['ALLOWED_HOSTS'] = ['127.0.0.1', 'localhost']
        module_globals['SESSION_COOKIE_AGE'] = 30 * 24 * 60 * 60
        if port:
            module_globals['CSRF_TRUSTED_ORIGINS'] = [
                f'http://127.0.0.1:{port}',
                f'http://localhost:{port}',
            ]
    elif mode == 'server':
        allowed_hosts = os.environ.get('COMMCARE_SYNC_ALLOWED_HOSTS', '*')
        module_globals['ALLOWED_HOSTS'] = [
            host.strip() for host in allowed_hosts.split(',') if host.strip()
        ]
        if _truthy(os.environ.get('COMMCARE_SYNC_BEHIND_PROXY', '')):
            module_globals['SECURE_PROXY_SSL_HEADER'] = (
                'HTTP_X_FORWARDED_PROTO',
                'https',
            )

    # --- Optional data-dir settings.py: exec'd last so it can override
    # anything above, except DATABASES (the app DB location is fixed for a
    # packaged install). The pre-exec snapshot is a deep copy compared by
    # value (not identity) after, so both reassignment (``DATABASES =
    # {...}``) and in-place mutation (``DATABASES['default']['NAME'] =
    # ...``) are caught.
    override_path = data_dir / DATA_DIR_SETTINGS_FILENAME
    if override_path.is_file():
        databases_before = copy.deepcopy(module_globals['DATABASES'])
        code = compile(override_path.read_text(), str(override_path), 'exec')
        exec(code, module_globals)  # noqa: S102
        if module_globals['DATABASES'] != databases_before:
            raise ImproperlyConfigured(
                f'{override_path} must not redefine DATABASES; the '
                'application database location is not overridable in a '
                'packaged install.'
            )
