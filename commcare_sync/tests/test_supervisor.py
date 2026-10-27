import subprocess
import sys
import threading
import time
from dataclasses import replace

import psutil
import pytest
from unmagic import fixture, use

from commcare_sync.launcher.instance import write_cluster_file
from commcare_sync.launcher.supervisor import (
    ClusterStillRunningError,
    ClusterSupervisor,
    SupervisorPolicy,
    run_cluster_until_stopped,
    stop_orphaned_cluster,
)
from commcare_sync.tests.helpers import (
    FAKE_PID,
    FAST,
    FakeProcess,
    fake_stop,
    wait_until,
)

_tmp_path = fixture('tmp_path')
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


SLEEPER = [sys.executable, '-c', 'import time; time.sleep(60)']


@use(_tmp_path)
class TestStopOrphanedCluster:
    def test_a_recorded_survivor_is_stopped(self):
        orphan = subprocess.Popen(SLEEPER)
        try:
            write_cluster_file(_tmp_path(), psutil.Process(orphan.pid))
            stop_orphaned_cluster(_tmp_path())
            # psutil reaps it, so the exit status is lost to Popen.
            orphan.wait(timeout=5)
        finally:
            if orphan.poll() is None:
                orphan.kill()
        assert not (_tmp_path() / 'cluster.json').exists()

    def test_a_record_of_a_dead_process_is_cleared(self):
        orphan = subprocess.Popen(SLEEPER)
        write_cluster_file(_tmp_path(), psutil.Process(orphan.pid))
        orphan.kill()
        orphan.wait()
        stop_orphaned_cluster(_tmp_path())
        assert not (_tmp_path() / 'cluster.json').exists()

    def test_no_record_is_fine(self):
        stop_orphaned_cluster(_tmp_path())

    @use(_monkeypatch)
    def test_a_survivor_that_cannot_be_stopped_is_an_error(self):
        # Startup maintenance would otherwise repair a database that the
        # survivor is still working on.
        _monkeypatch().setattr(
            'commcare_sync.launcher.supervisor.terminate_then_kill',
            lambda processes, timeout: processes,
        )
        orphan = subprocess.Popen(SLEEPER)
        try:
            write_cluster_file(_tmp_path(), psutil.Process(orphan.pid))
            with pytest.raises(ClusterStillRunningError) as exc_info:
                stop_orphaned_cluster(_tmp_path())
        finally:
            orphan.kill()
            orphan.wait()
        assert str(orphan.pid) in str(exc_info.value)
        assert (_tmp_path() / 'cluster.json').exists()


class FakeSentinel:
    alive = True

    def is_alive(self):
        return self.alive


class FakeCluster:
    def __init__(self):
        self.is_running = False
        self.sentinel = FakeSentinel()
        self.stopped = False

    def start(self):
        self.is_running = True

    def stop(self):
        self.stopped = True
        self.is_running = False


class FakeParent:
    def __init__(self, running=True):
        self.running = running

    def is_running(self):
        return self.running


class TestRunClusterUntilStopped:
    def test_exits_zero_once_the_cluster_stops_itself(self):
        cluster = FakeCluster()
        parent = FakeParent()

        def stop_soon():
            time.sleep(0.05)
            cluster.stop()  # as the SIGTERM handler would

        threading.Thread(target=stop_soon).start()
        assert run_cluster_until_stopped(cluster, parent, 0.01) == 0

    def test_stops_the_cluster_when_the_launcher_is_gone(self):
        cluster = FakeCluster()
        assert run_cluster_until_stopped(cluster, FakeParent(False), 0.01) == 1
        assert cluster.stopped

    def test_exits_nonzero_when_the_sentinel_dies(self):
        cluster = FakeCluster()
        cluster.sentinel.alive = False
        assert run_cluster_until_stopped(cluster, FakeParent(), 0.01) == 1

    def test_stops_the_cluster_when_the_watch_itself_fails(self):
        class BrokenParent:
            def is_running(self):
                raise RuntimeError('psutil exploded')

        cluster = FakeCluster()
        with pytest.raises(RuntimeError):
            run_cluster_until_stopped(cluster, BrokenParent(), 0.01)
        assert cluster.stopped
