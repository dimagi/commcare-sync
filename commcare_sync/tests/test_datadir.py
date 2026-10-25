from unmagic import fixture, use

from commcare_sync.launcher import datadir
from commcare_sync.launcher.datadir import resolve_data_dir
from commcare_sync.launcher.env import DATA_DIR_ENV_VAR
from commcare_sync.tests.fixtures import no_data_dir_env_var

_tmp_path = fixture('tmp_path')
_monkeypatch = fixture('monkeypatch')


@fixture
@use(no_data_dir_env_var, _tmp_path, _monkeypatch)
def platform_data_dir():
    platform = _tmp_path() / 'platform'

    def user_data_dir(appname, appauthor):
        # Without appauthor=False, Windows gets commcare-sync\commcare-sync.
        assert appauthor is False
        return str(platform)

    _monkeypatch().setattr(datadir, 'user_data_dir', user_data_dir)
    yield platform


@use(platform_data_dir)
class TestResolveDataDir:
    def test_cli_value_beats_env_var(self):
        _monkeypatch().setenv(DATA_DIR_ENV_VAR, str(_tmp_path() / 'from-env'))
        from_cli = _tmp_path() / 'from-cli'
        assert resolve_data_dir(from_cli) == from_cli

    def test_env_var_beats_platform_default(self):
        from_env = _tmp_path() / 'from-env'
        _monkeypatch().setenv(DATA_DIR_ENV_VAR, str(from_env))
        assert resolve_data_dir() == from_env

    def test_platform_default(self):
        assert resolve_data_dir() == platform_data_dir()

    def test_creates_subdirectories(self):
        data_dir = resolve_data_dir(_tmp_path() / 'new')
        assert (data_dir / 'logs').is_dir()
        assert (data_dir / 'media').is_dir()
