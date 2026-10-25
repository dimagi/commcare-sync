import stat
import sys

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from unmagic import fixture, use

from commcare_sync.launcher import secrets
from commcare_sync.launcher.secrets import bootstrap_secrets, load_secrets

_tmp_path = fixture('tmp_path')
_monkeypatch = fixture('monkeypatch')
_caplog = fixture('caplog')


@use(_tmp_path)
class TestBootstrapSecrets:
    def test_creates_usable_secrets(self):
        bootstrap_secrets(_tmp_path())
        loaded = load_secrets(_tmp_path())
        assert len(loaded['SECRET_KEY']) >= 50
        Fernet(loaded['FERNET_KEYS'][0])

    @pytest.mark.skipif(sys.platform == 'win32', reason='POSIX file modes')
    def test_file_is_readable_by_owner_only(self):
        bootstrap_secrets(_tmp_path())
        mode = stat.S_IMODE((_tmp_path() / 'secrets.json').stat().st_mode)
        assert mode == 0o600

    def test_never_rewrites_existing_secrets(self):
        bootstrap_secrets(_tmp_path())
        before = load_secrets(_tmp_path())
        bootstrap_secrets(_tmp_path())
        assert load_secrets(_tmp_path()) == before

    @use(_monkeypatch)
    def test_a_failed_write_leaves_no_file_behind(self):
        def dump(*args, **kwargs):
            raise OSError('disk full')

        _monkeypatch().setattr(secrets.json, 'dump', dump)
        with pytest.raises(OSError):
            bootstrap_secrets(_tmp_path())
        assert list(_tmp_path().iterdir()) == []

    @use(_monkeypatch, _caplog)
    def test_falls_back_when_the_filesystem_has_no_hard_links(self):
        def link(src, dst):
            raise PermissionError('hard links are not supported')

        _monkeypatch().setattr(secrets.os, 'link', link)
        with _caplog().at_level('INFO'):
            bootstrap_secrets(_tmp_path())
        assert [p.name for p in _tmp_path().iterdir()] == ['secrets.json']
        load_secrets(_tmp_path())
        assert 'hard links are not supported' in _caplog().text

    @use(_monkeypatch)
    def test_the_fallback_never_replaces_another_process_file(self):
        path = _tmp_path() / 'secrets.json'

        def link(src, dst):
            path.write_text('{"theirs": true}')  # another process wins
            raise PermissionError('hard links are not supported')

        _monkeypatch().setattr(secrets.os, 'link', link)
        bootstrap_secrets(_tmp_path())
        assert path.read_text() == '{"theirs": true}'

    def test_removes_a_temporary_file_left_by_a_crash(self):
        (_tmp_path() / '.secrets-abc123').write_text('{}')
        bootstrap_secrets(_tmp_path())
        assert [p.name for p in _tmp_path().iterdir()] == ['secrets.json']


@use(_tmp_path)
class TestLoadSecrets:
    @pytest.mark.parametrize('contents', ['', '{}', 'not json'])
    def test_an_unreadable_file_names_itself(self, contents):
        (_tmp_path() / 'secrets.json').write_text(contents)
        with pytest.raises(ImproperlyConfigured) as exc_info:
            load_secrets(_tmp_path())
        assert str(_tmp_path() / 'secrets.json') in str(exc_info.value)

    def test_a_missing_file_is_not_called_corrupt(self):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            load_secrets(_tmp_path())
        assert str(_tmp_path() / 'secrets.json') in str(exc_info.value)
        assert 'first run' in str(exc_info.value)
        assert 'backup' not in str(exc_info.value)
