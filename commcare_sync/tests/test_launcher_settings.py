"""Tests for launcher-mode settings (commcare_sync/settings.py tail +
commcare_sync/launcher/settings_overlay.py).

Settings are process-global in Django, so each scenario is exercised in a
fresh subprocess with crafted environment variables rather than by mutating
``django.conf.settings`` in-process.
"""

import json
import subprocess
import sys
from pathlib import Path

from commcare_sync.launcher.secrets import bootstrap_secrets

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

PROBE = """
import json
import django
django.setup()
from django.conf import settings
print(json.dumps({{
    {fields}
}}))
"""


def _run_probe(data_dir: Path, extra_env: dict, fields: dict) -> dict:
    """Run a settings probe subprocess and return the requested settings.

    ``fields`` maps output keys to Python expressions (strings) evaluated
    against ``settings`` inside the subprocess.
    """
    field_src = ',\n    '.join(
        f'{json.dumps(key)}: {expr}' for key, expr in fields.items()
    )
    script = PROBE.format(fields=field_src)

    env = {
        'PATH': subprocess_path(),
        'DJANGO_SETTINGS_MODULE': 'commcare_sync.settings',
        'COMMCARE_SYNC_DATA_DIR': str(data_dir),
    }
    env.update(extra_env)

    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise AssertionError(
            f'probe failed (exit {result.returncode}):\n{result.stderr}'
        )
    return json.loads(result.stdout)


def subprocess_path():
    import os

    return os.environ.get('PATH', '')


def _bootstrapped_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    bootstrap_secrets(data_dir)
    return data_dir


def test_sqlite_path_lands_in_data_dir_and_keeps_options(tmp_path):
    data_dir = _bootstrapped_data_dir(tmp_path)

    result = _run_probe(
        data_dir,
        {'COMMCARE_SYNC_MODE': 'desktop'},
        {
            'name': 'settings.DATABASES["default"]["NAME"]',
            'options': 'settings.DATABASES["default"]["OPTIONS"]',
        },
    )

    assert result['name'] == str(data_dir / 'db.sqlite3')
    assert result['options'] == {
        'init_command': (
            'PRAGMA journal_mode=WAL;'
            'PRAGMA busy_timeout=5000;'
            'PRAGMA synchronous=NORMAL;'
        ),
        'transaction_mode': 'IMMEDIATE',
    }


def test_desktop_mode_sets_allowed_hosts_and_csrf_origins(tmp_path):
    data_dir = _bootstrapped_data_dir(tmp_path)

    result = _run_probe(
        data_dir,
        {'COMMCARE_SYNC_MODE': 'desktop', 'COMMCARE_SYNC_PORT': '8123'},
        {
            'allowed_hosts': 'settings.ALLOWED_HOSTS',
            'csrf_origins': 'settings.CSRF_TRUSTED_ORIGINS',
            'debug': 'settings.DEBUG',
            'session_cookie_age': 'settings.SESSION_COOKIE_AGE',
        },
    )

    assert result['allowed_hosts'] == ['127.0.0.1', 'localhost']
    assert result['csrf_origins'] == [
        'http://127.0.0.1:8123',
        'http://localhost:8123',
    ]
    assert result['debug'] is False
    assert result['session_cookie_age'] == 30 * 24 * 60 * 60


def test_server_mode_parses_allowed_hosts_from_env(tmp_path):
    data_dir = _bootstrapped_data_dir(tmp_path)

    result = _run_probe(
        data_dir,
        {
            'COMMCARE_SYNC_MODE': 'server',
            'COMMCARE_SYNC_ALLOWED_HOSTS': 'example.com, www.example.com',
        },
        {'allowed_hosts': 'settings.ALLOWED_HOSTS'},
    )

    assert result['allowed_hosts'] == ['example.com', 'www.example.com']


def test_env_secret_key_beats_secrets_file(tmp_path):
    data_dir = _bootstrapped_data_dir(tmp_path)

    result = _run_probe(
        data_dir,
        {
            'COMMCARE_SYNC_MODE': 'server',
            'SECRET_KEY': 'env-provided-secret-key',
        },
        {'secret_key': 'settings.SECRET_KEY'},
    )

    assert result['secret_key'] == 'env-provided-secret-key'


def test_data_dir_settings_py_override_applies(tmp_path):
    data_dir = _bootstrapped_data_dir(tmp_path)
    (data_dir / 'settings.py').write_text('COMMCARE_SYNC_UI_PAGE_SIZE = 999\n')

    result = _run_probe(
        data_dir,
        {'COMMCARE_SYNC_MODE': 'server'},
        {'page_size': 'settings.COMMCARE_SYNC_UI_PAGE_SIZE'},
    )

    assert result['page_size'] == 999


def _run_setup_expecting_failure(
    data_dir: Path,
) -> subprocess.CompletedProcess:
    env = {
        'PATH': subprocess_path(),
        'DJANGO_SETTINGS_MODULE': 'commcare_sync.settings',
        'COMMCARE_SYNC_DATA_DIR': str(data_dir),
        'COMMCARE_SYNC_MODE': 'server',
    }
    return subprocess.run(
        [sys.executable, '-c', 'import django\ndjango.setup()\n'],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_data_dir_settings_py_redefining_databases_raises(tmp_path):
    data_dir = _bootstrapped_data_dir(tmp_path)
    (data_dir / 'settings.py').write_text(
        "DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', "
        "'NAME': 'elsewhere.sqlite3'}}\n"
    )

    result = _run_setup_expecting_failure(data_dir)

    assert result.returncode != 0
    assert 'ImproperlyConfigured' in result.stderr
    assert 'DATABASES' in result.stderr


def test_data_dir_settings_py_mutating_databases_in_place_raises(tmp_path):
    # The more natural way an operator would try to "just change the path" --
    # must be caught the same as a full reassignment of DATABASES.
    data_dir = _bootstrapped_data_dir(tmp_path)
    (data_dir / 'settings.py').write_text(
        "DATABASES['default']['NAME'] = '/somewhere/else.sqlite3'\n"
    )

    result = _run_setup_expecting_failure(data_dir)

    assert result.returncode != 0
    assert 'ImproperlyConfigured' in result.stderr
    assert 'DATABASES' in result.stderr
