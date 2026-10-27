import subprocess
import sys
import threading
import time
from dataclasses import replace

import psutil
from unmagic import fixture, use

from commcare_sync.launcher.supervisor import (
    ClusterSupervisor,
    SupervisorPolicy,
)
from commcare_sync.tests.helpers import (
    FAKE_PID,
    FAST,
    FakeProcess,
    fake_stop,
    wait_until,
)

_monkeypatch = fixture('monkeypatch')
_caplog = fixture('caplog')


def make_supervisor(processes, **policy):
    spawned = []

    def popen_factory():
        process = processes[min(len(spawned), len(processes) - 1)]
        spawned.append(process)
        return process

    supervisor = ClusterSupervisor(
        popen_factory=popen_factory,
        stop_tree=fake_stop,
        policy=replace(FAST, **policy),
    )
    return supervisor, spawned


STUBBORN_PARENT = """
import signal, subprocess, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
print(child.pid, flush=True)
time.sleep(60)
"""

ABSCONDING_PARENT = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
print(child.pid, flush=True)
time.sleep(0.5)
"""


class TestClusterSupervisor:
    def test_restarts_an_unexpected_exit(self):
        crashed = FakeProcess(exits_with=1)
        healthy = FakeProcess(pid=FAKE_PID + 1)
        supervisor, spawned = make_supervisor([crashed, healthy])
        supervisor.start()
        try:
            assert wait_until(lambda: spawned == [crashed, healthy])
            assert not supervisor.gave_up.is_set()
        finally:
            supervisor.stop()

    def test_gives_up_after_too_many_restarts(self):
        supervisor, spawned = make_supervisor(
            [FakeProcess(exits_with=1)], max_restarts=3
        )
        supervisor.start()
        try:
            assert wait_until(supervisor.gave_up.is_set)
            assert len(spawned) == 4  # the first start and three restarts
            time.sleep(0.05)
            assert len(spawned) == 4
        finally:
            supervisor.stop()

    def test_restarts_outside_the_window_do_not_count_together(self):
        supervisor, spawned = make_supervisor(
            [FakeProcess(exits_with=1)], max_restarts=1, restart_window=0
        )
        supervisor.start()
        try:
            assert wait_until(lambda: len(spawned) > 3)
            assert not supervisor.gave_up.is_set()
        finally:
            supervisor.stop()

    def test_stop_terminates_the_child(self):
        healthy = FakeProcess()
        supervisor, spawned = make_supervisor([healthy])
        supervisor.start()
        supervisor.stop()
        assert healthy.stopped
        assert len(spawned) == 1

    def test_a_stop_during_a_restart_does_not_orphan_the_new_child(self):
        crashed = FakeProcess(exits_with=1)
        replacement = FakeProcess(pid=FAKE_PID + 1)
        spawned = []

        def popen_factory():
            if not spawned:
                spawned.append(crashed)
                return crashed
            supervisor._stopping.set()  # a stop lands mid-spawn
            spawned.append(replacement)
            return replacement

        supervisor = ClusterSupervisor(
            popen_factory=popen_factory, stop_tree=fake_stop, policy=FAST
        )
        supervisor.start()
        try:
            assert wait_until(lambda: replacement.stopped)
            assert spawned == [crashed, replacement]
        finally:
            supervisor.stop()

    def test_a_crash_in_the_supervisor_counts_as_giving_up(self):
        class BrokenProcess(FakeProcess):
            def poll(self):
                raise RuntimeError('psutil exploded')

        supervisor, _spawned = make_supervisor([BrokenProcess()])
        supervisor.start()
        assert wait_until(supervisor.gave_up.is_set)

    def test_a_stop_before_the_first_spawn_starts_no_child(self):
        supervisor, spawned = make_supervisor([FakeProcess()])
        supervisor.stop()
        supervisor.start()
        supervisor.stop()
        assert spawned == []

    def test_a_failed_respawn_counts_as_giving_up(self):
        crashed = FakeProcess(exits_with=1)
        spawned = []

        def popen_factory():
            if spawned:
                raise OSError('cannot start the cluster')
            spawned.append(crashed)
            return crashed

        supervisor = ClusterSupervisor(
            popen_factory=popen_factory,
            stop_tree=fake_stop,
            policy=replace(FAST, max_restarts=3),
        )
        supervisor.start()
        try:
            assert wait_until(supervisor.gave_up.is_set)
        finally:
            supervisor.stop()

    def test_stop_leaves_no_descendant_processes(self):
        process = subprocess.Popen(
            [sys.executable, '-c', STUBBORN_PARENT],
            stdout=subprocess.PIPE,
            text=True,
        )
        grandchild_pid = int(process.stdout.readline())
        supervisor = ClusterSupervisor(
            popen_factory=lambda: process,
            policy=SupervisorPolicy(stop_timeout=0.5),
        )
        supervisor.start()
        supervisor.stop()
        assert wait_until(lambda: not psutil.pid_exists(grandchild_pid))
        assert process.poll() is not None

    def test_descendants_of_a_crashed_cluster_are_stopped(self):
        spawned = []

        def popen_factory():
            spawned.append(
                subprocess.Popen(
                    [sys.executable, '-c', ABSCONDING_PARENT],
                    stdout=subprocess.PIPE,
                    text=True,
                )
            )
            return spawned[-1]

        supervisor = ClusterSupervisor(
            popen_factory=popen_factory,
            policy=SupervisorPolicy(
                max_restarts=0, backoff=0, poll_interval=0.01, stop_timeout=1
            ),
        )
        supervisor.start()
        try:
            grandchild_pid = int(spawned[0].stdout.readline())
            assert wait_until(supervisor.gave_up.is_set)
            assert wait_until(lambda: not psutil.pid_exists(grandchild_pid))
        finally:
            supervisor.stop()

    @use(_monkeypatch, _caplog)
    def test_stop_warns_when_the_supervisor_thread_outlives_the_join(self):
        # The thread is still stopping the survivors of a crash.
        blocked = threading.Event()
        released = threading.Event()

        def block(processes, timeout):
            blocked.set()
            released.wait()
            return []

        class Survivor:
            def is_running(self):
                return True

        class CrashesAfterAFewPolls(FakeProcess):
            polls = 0

            def poll(self):
                self.polls += 1
                return 1 if self.polls > 2 else None

        _monkeypatch().setattr(
            'commcare_sync.launcher.supervisor.descendants',
            lambda pid: [Survivor()],
        )
        _monkeypatch().setattr(
            'commcare_sync.launcher.supervisor.terminate_then_kill', block
        )
        supervisor, _spawned = make_supervisor([CrashesAfterAFewPolls()])
        supervisor.start()
        try:
            assert blocked.wait(timeout=5)
            with _caplog().at_level('WARNING'):
                supervisor.stop()
        finally:
            released.set()
        assert 'supervisor is still stopping' in _caplog().text
