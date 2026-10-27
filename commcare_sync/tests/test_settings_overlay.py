import copy
import logging
import logging.config
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured
from unmagic import fixture, use

from commcare_sync.consts import SetupAccess
from commcare_sync.launcher.env import MODE_ENV_VAR, PORT_ENV_VAR, Mode
from commcare_sync.launcher.secrets import bootstrap_secrets, load_secrets
from commcare_sync.launcher.settings_overlay import apply_launcher_overlay

_tmp_path = fixture('tmp_path')

BASE_SETTINGS = {
    'DEBUG': True,
    'ALLOWED_HOSTS': [],
    'DATABASES': {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': '/checkout/db.sqlite3',
            'OPTIONS': {'transaction_mode': 'IMMEDIATE'},
        }
    },
    'LOG_DIR': '/checkout/logs',
    'MEDIA_ROOT': '/checkout/media',
    'STATIC_ROOT': '/checkout/static_root',
}


@fixture
@use(_tmp_path)
def data_dir():
    (_tmp_path() / 'logs').mkdir()  # as resolve_data_dir() does
    bootstrap_secrets(_tmp_path())
    yield _tmp_path()


def overlay(mode=Mode.SERVER, port='8000', **environ):
    settings = copy.deepcopy(BASE_SETTINGS)
    if mode is not None:
        environ[MODE_ENV_VAR] = mode
    if port is not None:
        environ[PORT_ENV_VAR] = port
    apply_launcher_overlay(data_dir(), settings, environ)
    return settings


@use(data_dir)
class TestOverlay:
    def test_relocates_files_into_the_data_dir(self):
        settings = overlay()
        assert settings['DATABASES']['default']['NAME'] == str(
            data_dir() / 'db.sqlite3'
        )
        assert settings['DATABASES']['default']['OPTIONS'] == {
            'transaction_mode': 'IMMEDIATE'
        }
        assert settings['LOG_DIR'] == str(data_dir() / 'logs')
        assert settings['MEDIA_ROOT'] == str(data_dir() / 'media')
        assert settings['STATIC_ROOT'] == str(data_dir() / 'static_root')

    def test_reads_secrets_from_the_data_dir(self):
        settings = overlay()
        secrets = load_secrets(data_dir())
        assert settings['SECRET_KEY'] == secrets['SECRET_KEY']
        assert settings['FERNET_KEYS'] == secrets['FERNET_KEYS']

    def test_env_var_secrets_win(self):
        settings = overlay(SECRET_KEY='from-env')
        assert 'SECRET_KEY' not in settings
        assert (
            settings['FERNET_KEYS'] == load_secrets(data_dir())['FERNET_KEYS']
        )

    def test_env_var_secrets_need_no_file(self):
        (data_dir() / 'secrets.json').unlink()
        settings = overlay(SECRET_KEY='from-env', FERNET_KEYS='["k"]')
        assert 'SECRET_KEY' not in settings
        assert 'FERNET_KEYS' not in settings

    def test_runs_as_a_server_without_a_mode(self):
        assert overlay(mode=None)['ALLOWED_HOSTS'] == ['*']

    def test_an_unknown_mode_is_rejected(self):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            overlay(mode='dekstop')
        assert 'dekstop' in str(exc_info.value)

    def test_logs_warnings_to_a_file_in_the_data_dir(self):
        logging_config = overlay()['LOGGING']
        [handler_name] = logging_config['root']['handlers']
        handler = logging_config['handlers'][handler_name]
        assert handler['filename'] == str(data_dir() / 'logs' / 'app.log')
        assert logging_config['root']['level'] == 'WARNING'
        logger = logging.getLogger('django.request')
        logging.config.dictConfig(logging_config)
        try:
            logger.error('an unhandled error')
        finally:
            logging.config.dictConfig(
                {
                    'version': 1,
                    'disable_existing_loggers': False,
                    'root': {'handlers': []},
                }
            )
        assert (
            'an unhandled error'
            in (data_dir() / 'logs' / 'app.log').read_text()
        )

    def test_names_its_cookies(self):
        settings = overlay()
        assert settings['SESSION_COOKIE_NAME'] == 'commcare_sync_sessionid'
        assert settings['CSRF_COOKIE_NAME'] == 'commcare_sync_csrftoken'

    def test_data_dir_settings_file_overrides(self):
        (data_dir() / 'settings.py').write_text(
            "ALLOWED_HOSTS = ['only.example.com']\n"
        )
        assert overlay()['ALLOWED_HOSTS'] == ['only.example.com']

    @pytest.mark.parametrize(
        'override',
        [
            "DATABASES = {'default': {'ENGINE': 'x'}}",
            "DATABASES['default']['NAME'] = '/elsewhere.sqlite3'",
        ],
    )
    def test_data_dir_settings_file_cannot_move_the_database(self, override):
        (data_dir() / 'settings.py').write_text(override + '\n')
        with pytest.raises(ImproperlyConfigured):
            overlay()

    @pytest.mark.parametrize(
        'contents, complaint',
        [
            ("ALLOWED_HOSTS = ['only.example.com'\n", 'SyntaxError'),
            ('ALLOWED_HOSTS = HOSTS\n', "NameError: name 'HOSTS'"),
        ],
    )
    def test_a_broken_data_dir_settings_file_names_itself(
        self, contents, complaint
    ):
        # A desktop build has no console: the log must say which file.
        (data_dir() / 'settings.py').write_text(contents)
        with pytest.raises(ImproperlyConfigured) as exc_info:
            overlay()
        assert str(data_dir() / 'settings.py') in str(exc_info.value)
        assert complaint in str(exc_info.value)

    @pytest.mark.skipif(sys.platform == 'win32', reason='POSIX file modes')
    def test_a_world_writable_data_dir_settings_file_is_refused(self):
        # It is run as code.
        path = data_dir() / 'settings.py'
        path.write_text('')
        path.chmod(0o666)
        with pytest.raises(ImproperlyConfigured) as exc_info:
            overlay()
        assert str(path) in str(exc_info.value)
        assert 'run as code' in str(exc_info.value)

    @pytest.mark.skipif(sys.platform == 'win32', reason='POSIX file modes')
    def test_a_group_writable_data_dir_settings_file_is_fine(self):
        # The default on Ubuntu, where the group is the user's own.
        path = data_dir() / 'settings.py'
        path.write_text('')
        path.chmod(0o664)
        overlay()

    @pytest.mark.skipif(sys.platform == 'win32', reason='POSIX file modes')
    def test_a_world_writable_data_dir_is_refused(self):
        # Anyone could replace settings.py in it.
        (data_dir() / 'settings.py').write_text('')
        data_dir().chmod(0o777)
        try:
            with pytest.raises(ImproperlyConfigured) as exc_info:
                overlay()
        finally:
            data_dir().chmod(0o700)
        assert str(data_dir()) in str(exc_info.value)

    @pytest.mark.skipif(sys.platform == 'win32', reason='POSIX file modes')
    def test_permissions_matter_only_with_a_data_dir_settings_file(self):
        data_dir().chmod(0o777)
        try:
            overlay()
        finally:
            data_dir().chmod(0o700)


@use(data_dir)
class TestDesktopMode:
    def test_is_local_only(self):
        settings = overlay(mode=Mode.DESKTOP, port='43210')
        assert settings['DEBUG'] is False
        assert settings['ALLOWED_HOSTS'] == ['localhost', '127.0.0.1', '[::1]']
        assert settings['CSRF_TRUSTED_ORIGINS'] == [
            'http://localhost:43210',
            'http://127.0.0.1:43210',
            'http://[::1]:43210',
        ]


@use(data_dir)
class TestServerMode:
    def test_allows_configured_hosts(self):
        settings = overlay(
            COMMCARE_SYNC_ALLOWED_HOSTS='sync.example.com, 10.0.0.5'
        )
        assert settings['DEBUG'] is False
        assert settings['ALLOWED_HOSTS'] == ['sync.example.com', '10.0.0.5']

    def test_allows_any_host_by_default(self):
        assert overlay()['ALLOWED_HOSTS'] == ['*']

    def test_behind_proxy(self):
        settings = overlay(COMMCARE_SYNC_BEHIND_PROXY='true')
        assert settings['SECURE_PROXY_SSL_HEADER'] == (
            'HTTP_X_FORWARDED_PROTO',
            'https',
        )

    @pytest.mark.parametrize('value', ['on', 'maybe'])
    def test_an_unrecognised_proxy_flag_is_rejected(self, value):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            overlay(COMMCARE_SYNC_BEHIND_PROXY=value)
        assert value in str(exc_info.value)
        assert "''" not in str(exc_info.value)

    def test_the_setup_page_needs_the_launcher_token(self):
        assert overlay()['SETUP_PAGE_ACCESS'] == SetupAccess.TOKEN

    def test_behind_a_proxy_every_client_looks_local_so_nobody_may_set_up(
        self,
    ):
        settings = overlay(COMMCARE_SYNC_BEHIND_PROXY='true')
        assert settings['SETUP_PAGE_ACCESS'] == SetupAccess.NOBODY


@use(data_dir)
class TestSetupPageInDesktopMode:
    def test_needs_the_launcher_token_too(self):
        settings = overlay(mode=Mode.DESKTOP)
        assert settings['SETUP_PAGE_ACCESS'] == SetupAccess.TOKEN


@use(data_dir)
class TestSetupToken:
    @pytest.mark.parametrize('mode', [Mode.SERVER, Mode.DESKTOP])
    def test_comes_from_the_environment(self, mode):
        settings = overlay(mode=mode, COMMCARE_SYNC_SETUP_TOKEN='abc')
        assert settings['SETUP_TOKEN'] == 'abc'

    def test_is_none_without_the_launcher(self):
        assert overlay()['SETUP_TOKEN'] is None
