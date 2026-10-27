"""
Settings for an install that runs from a data directory: the launcher,
or ``manage.py`` with ``COMMCARE_SYNC_DATA_DIR`` set.

When ``COMMCARE_SYNC_DATA_DIR`` is set, ``commcare_sync.settings`` calls
``apply_launcher_overlay()`` instead of importing ``settings_local``.
Precedence, lowest first: the defaults in ``settings.py``; this overlay,
which reads ``secrets.json`` (unless ``SECRET_KEY`` and ``FERNET_KEYS`` are
in the environment) and the ``COMMCARE_SYNC_*`` environment variables;
then ``settings.py`` in the data directory, which overrides anything
except ``DATABASES``.
"""

import copy
import os
import stat
from collections.abc import Mapping
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from commcare_sync.consts import LOCAL_HOSTNAMES, SetupAccess
from commcare_sync.launcher.env import (
    ALLOWED_HOSTS_ENV_VAR,
    APP_LOG_FILENAME,
    BEHIND_PROXY_ENV_VAR,
    DATABASE_FILENAME,
    LOG_FORMAT,
    LOGS_DIRNAME,
    MEDIA_DIRNAME,
    MODE_ENV_VAR,
    PORT_ENV_VAR,
    STATIC_ROOT_DIRNAME,
    Mode,
)
from commcare_sync.launcher.secrets import SECRET_NAMES, load_secrets

DATA_DIR_SETTINGS_FILENAME = 'settings.py'
# A desktop user is not asked to sign in again for a month.
DESKTOP_SESSION_AGE = 30 * 24 * 60 * 60
TRUE_VALUES = ('1', 'true', 'yes')
FALSE_VALUES = ('', '0', 'false', 'no')


def apply_launcher_overlay(
    data_dir: Path, settings: dict, environ: Mapping[str, str]
) -> None:
    """
    Mutates ``settings``, the settings module's globals. ``data_dir``
    already exists. Without a mode (``manage.py`` against a data
    directory) it runs as the server would.
    """
    mode = _parse_mode(environ.get(MODE_ENV_VAR, Mode.SERVER))
    settings['DEBUG'] = False
    _apply_paths(data_dir, settings)
    _apply_cookie_names(settings)
    _apply_secrets(data_dir, settings, environ)
    if mode == Mode.DESKTOP:
        _apply_desktop(settings, environ)
    else:
        _apply_server(settings, environ)
    _exec_data_dir_settings(data_dir / DATA_DIR_SETTINGS_FILENAME, settings)


def _apply_paths(data_dir: Path, settings: dict) -> None:
    settings['DATABASES']['default']['NAME'] = str(
        data_dir / DATABASE_FILENAME
    )
    settings['LOG_DIR'] = str(data_dir / LOGS_DIRNAME)
    settings['MEDIA_ROOT'] = str(data_dir / MEDIA_DIRNAME)
    # The code may be installed read-only; the data directory is ours.
    settings['STATIC_ROOT'] = str(data_dir / STATIC_ROOT_DIRNAME)
    settings['LOGGING'] = _logging(data_dir)


def _apply_cookie_names(settings: dict) -> None:
    # Cookies are not isolated by port, so a browser sends the default
    # names to every other local web app too, and another Django app on
    # the same host would overwrite them.
    settings['SESSION_COOKIE_NAME'] = 'commcare_sync_sessionid'
    settings['CSRF_COOKIE_NAME'] = 'commcare_sync_csrftoken'


def _apply_secrets(
    data_dir: Path, settings: dict, environ: Mapping[str, str]
) -> None:
    """``secrets.json`` supplies whichever secrets the environment does not."""
    missing = [name for name in SECRET_NAMES if name not in environ]
    if missing:
        secrets = load_secrets(data_dir)
        for name in missing:
            settings[name] = secrets[name]


def _apply_desktop(settings: dict, environ: Mapping[str, str]) -> None:
    settings['ALLOWED_HOSTS'] = list(LOCAL_HOSTNAMES)
    settings['SESSION_COOKIE_AGE'] = DESKTOP_SESSION_AGE
    port = environ.get(PORT_ENV_VAR)
    if port:
        settings['CSRF_TRUSTED_ORIGINS'] = [
            f'http://{host}:{port}' for host in LOCAL_HOSTNAMES
        ]


def _apply_server(settings: dict, environ: Mapping[str, str]) -> None:
    hosts = environ.get(ALLOWED_HOSTS_ENV_VAR, '*')
    settings['ALLOWED_HOSTS'] = [
        host.strip() for host in hosts.split(',') if host.strip()
    ]
    behind_proxy = _flag(environ, BEHIND_PROXY_ENV_VAR)
    # Behind a reverse proxy on the same machine every request
    # arrives from loopback, so nobody may use the setup page.
    settings['SETUP_PAGE_ACCESS'] = (
        SetupAccess.NOBODY if behind_proxy else SetupAccess.LOOPBACK
    )
    if behind_proxy:
        settings['SECURE_PROXY_SSL_HEADER'] = (
            'HTTP_X_FORWARDED_PROTO',
            'https',
        )


def _parse_mode(value: str) -> Mode:
    try:
        return Mode(value)
    except ValueError:
        raise ImproperlyConfigured(
            f'{MODE_ENV_VAR} is {value!r}; expected one of '
            f'{[m.value for m in Mode]}'
        ) from None


def _flag(environ: Mapping[str, str], name: str) -> bool:
    value = environ.get(name, '').strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(
        f'{name} is {environ[name]!r}; expected one of '
        f'{[v for v in TRUE_VALUES + FALSE_VALUES if v]}'
    )


def _logging(data_dir: Path) -> dict:
    """
    With ``DEBUG`` off, Django's default logging writes nothing to a
    file, and a desktop build has no console. One file for the web and
    cluster processes, which both load these settings. No rotation: the
    processes share the file, and rotating it from either would race the
    other.
    """
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {'default': {'format': LOG_FORMAT}},
        'handlers': {
            'file': {
                'class': 'logging.FileHandler',
                'filename': str(data_dir / LOGS_DIRNAME / APP_LOG_FILENAME),
                'encoding': 'utf-8',
                'formatter': 'default',
            },
        },
        'root': {'handlers': ['file'], 'level': 'WARNING'},
    }


def _exec_data_dir_settings(path: Path, settings: dict) -> None:
    """
    Runs last so it can override anything, except ``DATABASES``: the
    application database lives in the data directory, full stop.
    """
    if not path.is_file():
        return
    _refuse_if_others_may_write(path)
    databases_before = copy.deepcopy(settings['DATABASES'])
    try:
        exec(compile(path.read_text(), str(path), 'exec'), settings)  # noqa: S102
    except Exception as err:
        raise ImproperlyConfigured(
            f'{path} failed: {type(err).__name__}: {err}'
        ) from err
    if settings['DATABASES'] != databases_before:
        raise ImproperlyConfigured(f'{path} must not redefine DATABASES.')


def _refuse_if_others_may_write(path: Path) -> None:
    """
    The file is run as code, so it and its directory must belong to this
    user (or root) and not be writable by everyone. Windows keeps
    permissions in ACLs, which ``st_mode`` does not show.
    """
    if os.name != 'posix':
        return
    for candidate in (path, path.parent):
        status = candidate.stat()
        if status.st_uid not in (os.geteuid(), 0) or (
            status.st_mode & stat.S_IWOTH
        ):
            raise ImproperlyConfigured(
                f'{candidate} must be owned by you and not world-writable, '
                f'because {path.name} is run as code.'
            )
