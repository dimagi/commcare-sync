import os
from pathlib import Path

from commcare_sync.launcher.datadir import DATA_DIR_ENV_VAR, resolve_data_dir


def test_cli_value_takes_precedence_over_env(tmp_path, monkeypatch):
    cli_dir = tmp_path / 'from-cli'
    env_dir = tmp_path / 'from-env'
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(env_dir))

    result = resolve_data_dir(cli_value=cli_dir)

    assert result == cli_dir.resolve()


def test_env_value_used_when_no_cli_value(tmp_path, monkeypatch):
    env_dir = tmp_path / 'from-env'
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(env_dir))

    result = resolve_data_dir()

    assert result == env_dir.resolve()


def test_platformdirs_used_when_no_cli_value_or_env(tmp_path, monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)
    fake_default = tmp_path / 'platformdirs-default'
    monkeypatch.setattr(
        'commcare_sync.launcher.datadir.user_data_dir',
        lambda app_name: str(fake_default),
    )

    result = resolve_data_dir()

    assert result == fake_default.resolve()


def test_creates_directory_and_subdirs(tmp_path, monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)
    data_dir = tmp_path / 'new-data-dir'
    assert not data_dir.exists()

    result = resolve_data_dir(cli_value=data_dir)

    assert result.is_dir()
    assert (result / 'logs').is_dir()
    assert (result / 'media').is_dir()


def test_idempotent_when_directory_already_exists(tmp_path, monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)
    data_dir = tmp_path / 'existing-data-dir'
    data_dir.mkdir()
    (data_dir / 'logs').mkdir()

    result = resolve_data_dir(cli_value=data_dir)

    assert result.is_dir()
    assert (result / 'logs').is_dir()
    assert (result / 'media').is_dir()


def test_exports_resolved_path_to_environment(tmp_path, monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)
    data_dir = tmp_path / 'exported-data-dir'

    result = resolve_data_dir(cli_value=data_dir)

    assert os.environ[DATA_DIR_ENV_VAR] == str(result)


def test_returns_path_instance(tmp_path, monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)
    data_dir = tmp_path / 'path-type-data-dir'

    result = resolve_data_dir(cli_value=data_dir)

    assert isinstance(result, Path)


def test_expands_user_in_cli_value(tmp_path, monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))

    result = resolve_data_dir(cli_value='~/data-dir-via-home')

    assert result == (tmp_path / 'data-dir-via-home').resolve()
