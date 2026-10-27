import subprocess
import sys

import psutil
from unmagic import fixture, use

from commcare_sync.launcher.processes import (
    descendants,
    stop_process_tree,
    terminate_then_kill,
)
from commcare_sync.tests.helpers import FAKE_PID

_caplog = fixture('caplog')

IGNORES_SIGTERM = [
    sys.executable,
    '-c',
    'import signal, time\n'
    'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
    'time.sleep(60)',
]


class UnstoppableProcess:
    """As psutil reports a process that belongs to another user."""

    def __init__(self, pid):
        self.pid = pid

    def terminate(self):
        raise psutil.AccessDenied(self.pid)

    def kill(self):
        raise psutil.AccessDenied(self.pid)

    def wait(self, timeout=None):
        raise psutil.TimeoutExpired(timeout, self.pid)

    def is_running(self):
        return True


def test_a_gone_pid_has_no_descendants():
    assert descendants(FAKE_PID) == []


def test_stop_process_tree_kills_what_ignores_sigterm():
    process = subprocess.Popen(IGNORES_SIGTERM)
    stop_process_tree(process, timeout=0.2)
    assert process.poll() is not None


def test_stop_process_tree_copes_with_a_reaped_child():
    process = subprocess.Popen([sys.executable, '-c', ''])
    process.wait()
    stop_process_tree(process, timeout=0.2)


@use(_caplog)
def test_a_process_that_cannot_be_stopped_is_returned_and_logged():
    stubborn = UnstoppableProcess(FAKE_PID)
    with _caplog().at_level('WARNING'):
        survivors = terminate_then_kill([stubborn], timeout=0.01)
    assert survivors == [stubborn]
    assert f'Could not stop pid {FAKE_PID}' in _caplog().text
    assert f'[{FAKE_PID}] survived being killed' in _caplog().text
