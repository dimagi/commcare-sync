import time
from dataclasses import replace

from commcare_sync.launcher.supervisor import ClusterSupervisor
from commcare_sync.tests.helpers import FAST, FakeProcess, wait_until


def make_supervisor(processes, **policy):
    spawned = []

    def popen_factory():
        process = processes[min(len(spawned), len(processes) - 1)]
        spawned.append(process)
        return process

    supervisor = ClusterSupervisor(
        popen_factory=popen_factory, policy=replace(FAST, **policy)
    )
    return supervisor, spawned


class TestClusterSupervisor:
    def test_restarts_an_unexpected_exit(self):
        crashed = FakeProcess(pid=1, exits_with=1)
        healthy = FakeProcess(pid=2)
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
        assert healthy.terminated
        assert not healthy.killed
        assert len(spawned) == 1

    def test_a_stop_during_a_restart_does_not_orphan_the_new_child(self):
        crashed = FakeProcess(pid=1, exits_with=1)
        replacement = FakeProcess(pid=2)
        spawned = []

        def popen_factory():
            if not spawned:
                spawned.append(crashed)
                return crashed
            supervisor._stopping.set()  # a stop lands mid-spawn
            spawned.append(replacement)
            return replacement

        supervisor = ClusterSupervisor(popen_factory=popen_factory, policy=FAST)
        supervisor.start()
        try:
            assert wait_until(lambda: replacement.terminated)
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

    def test_stop_kills_a_child_that_ignores_sigterm(self):
        stubborn = FakeProcess(hangs_on_terminate=True)
        supervisor, _spawned = make_supervisor([stubborn])
        supervisor.start()
        supervisor.stop()
        assert stubborn.terminated
        assert stubborn.killed
