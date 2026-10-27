import json

import pytest
from unmagic import fixture, use

from commcare_sync.launcher import instance
from commcare_sync.launcher.instance import (
    acquire_instance_lock,
    read_instance_port,
    remove_instance_file,
    write_instance_file,
)

_tmp_path = fixture('tmp_path')
_caplog = fixture('caplog')
_monkeypatch = fixture('monkeypatch')


@use(_tmp_path)
def test_write_then_read_back():
    write_instance_file(_tmp_path(), port=12345, pid=999)
    contents = json.loads((_tmp_path() / 'instance.json').read_text())
    assert contents == {'port': 12345, 'pid': 999}
    assert read_instance_port(_tmp_path()) == 12345
    assert [p.name for p in _tmp_path().iterdir()] == ['instance.json']


@use(_tmp_path, _monkeypatch)
def test_a_failed_write_leaves_the_previous_record_whole():
    write_instance_file(_tmp_path(), port=12345, pid=999)

    def replace(src, dst):
        raise OSError('disk full')

    _monkeypatch().setattr(instance.os, 'replace', replace)
    with pytest.raises(OSError):
        write_instance_file(_tmp_path(), port=54321, pid=1000)
    assert read_instance_port(_tmp_path()) == 12345
    assert [p.name for p in _tmp_path().iterdir()] == ['instance.json']


@use(_tmp_path)
def test_remove_is_idempotent():
    write_instance_file(_tmp_path(), port=12345, pid=999)
    remove_instance_file(_tmp_path())
    remove_instance_file(_tmp_path())
    assert not (_tmp_path() / 'instance.json').exists()


@use(_tmp_path)
def test_missing_file_has_no_port():
    assert read_instance_port(_tmp_path()) is None


@pytest.mark.parametrize(
    'contents',
    [
        'not json',
        json.dumps({'pid': 1}),
        json.dumps({'port': 'not-a-port', 'pid': 1}),
        json.dumps({'port': True, 'pid': 1}),
    ],
)
@use(_tmp_path, _caplog)
def test_unusable_file_has_no_port_and_is_logged(contents):
    (_tmp_path() / 'instance.json').write_text(contents)
    with _caplog().at_level('WARNING'):
        assert read_instance_port(_tmp_path()) is None
    assert str(_tmp_path() / 'instance.json') in _caplog().text


@use(_tmp_path)
def test_the_lock_is_exclusive_until_released():
    first = acquire_instance_lock(_tmp_path())
    assert first is not None
    assert acquire_instance_lock(_tmp_path()) is None
    first.close()
    second = acquire_instance_lock(_tmp_path())
    assert second is not None
    second.close()

