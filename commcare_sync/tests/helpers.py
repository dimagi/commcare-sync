"""
Helpers for tests of the launcher.
"""

import signal
import socket
import time

from commcare_sync.consts import LOOPBACK_IPV4
from commcare_sync.launcher.supervisor import SupervisorPolicy

# Above any real pid, so that psutil never finds a process behind a fake.
FAKE_PID = 2**22 + 1


class FakeProcess:
    def __init__(self, pid=FAKE_PID, exits_with=None):
        self.pid = pid
        self.returncode = exits_with
        self.stopped = False

    def poll(self):
        return self.returncode


def fake_stop(process, timeout):
    process.stopped = True
    process.returncode = -signal.SIGTERM


def wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


# Fast timings for tests; fake_stop keeps psutil away from fake pids.
FAST = SupervisorPolicy(backoff=0, poll_interval=0.01, stop_timeout=0.05)


def listening_socket(host=LOOPBACK_IPV4):
    family = socket.AF_INET6 if ':' in host else socket.AF_INET
    taken = socket.socket(family, socket.SOCK_STREAM)
    taken.bind((host, 0))
    taken.listen(1)
    return taken
