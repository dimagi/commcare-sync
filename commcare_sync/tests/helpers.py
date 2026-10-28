"""
Helpers for tests of the launcher.
"""

import signal
import socket
import subprocess
import time

from commcare_sync.consts import LOOPBACK_IPV4
from commcare_sync.launcher.supervisor import SupervisorPolicy


class FakeProcess:
    def __init__(self, pid=4242, exits_with=None, hangs_on_terminate=False):
        self.pid = pid
        self.returncode = exits_with
        self.hangs_on_terminate = hangs_on_terminate
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        if not self.hangs_on_terminate:
            self.returncode = -signal.SIGTERM

    def kill(self):
        self.killed = True
        self.returncode = -signal.SIGKILL

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired(cmd='qcluster', timeout=timeout)
        return self.returncode


def wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


# Fast timings for tests.
FAST = SupervisorPolicy(backoff=0, poll_interval=0.01, stop_timeout=0.05)


def listening_socket(host=LOOPBACK_IPV4):
    family = socket.AF_INET6 if ':' in host else socket.AF_INET
    taken = socket.socket(family, socket.SOCK_STREAM)
    taken.bind((host, 0))
    taken.listen(1)
    return taken
