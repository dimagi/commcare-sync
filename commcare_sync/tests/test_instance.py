import json

import psutil
import pytest
from unmagic import fixture, use

from commcare_sync.launcher import instance
from commcare_sync.launcher.instance import (
    acquire_instance_lock,
    read_cluster_process,
    read_instance_port,
    remove_cluster_file,
    remove_instance_file,
    write_cluster_file,
    write_instance_file,
)
from commcare_sync.tests.helpers import FAKE_PID

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


@use(_tmp_path)
class TestClusterFile:
    def test_a_running_process_is_found(self):
        write_cluster_file(_tmp_path(), psutil.Process())
        found = read_cluster_process(_tmp_path())
        assert found is not None
        assert found.pid == psutil.Process().pid

    def test_a_process_that_has_exited_is_not(self):
        write_cluster_file(_tmp_path(), psutil.Process())
        remove_cluster_file(_tmp_path())
        assert read_cluster_process(_tmp_path()) is None

    def test_a_reused_pid_is_not(self):
        me = psutil.Process()
        record = {'pid': me.pid, 'create_time': me.create_time() - 1}
        (_tmp_path() / 'cluster.json').write_text(json.dumps(record))
        assert read_cluster_process(_tmp_path()) is None

    def test_a_dead_pid_is_not(self):
        record = {'pid': FAKE_PID, 'create_time': 0}
        (_tmp_path() / 'cluster.json').write_text(json.dumps(record))
        assert read_cluster_process(_tmp_path()) is None

    @use(_caplog)
    @pytest.mark.parametrize(
        'contents', ['not json', '[]', '{"pid": 1}', '{"pid": "x"}']
    )
    def test_an_unusable_file_is_nobody_and_is_logged(self, contents):
        (_tmp_path() / 'cluster.json').write_text(contents)
        with _caplog().at_level('WARNING'):
            assert read_cluster_process(_tmp_path()) is None
        assert str(_tmp_path() / 'cluster.json') in _caplog().text
