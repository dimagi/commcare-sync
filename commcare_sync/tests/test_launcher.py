"""Tests for the launcher entry point (commcare_sync/launcher/__init__.py)."""

import os
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from commcare_sync.launcher import (
    DEFAULT_PORT,
    DEFAULT_SERVER_BIND,
    DESKTOP,
    LOOPBACK,
    SERVER,
    ClusterSupervisor,
    PortUnavailableError,
    build_parser,
    find_free_port,
    main,
    port_is_available,
    resolve_listen_address,
    run_until_shutdown,
    server_url,
)
from commcare_sync.launcher.maintenance import DISPATCHER_FUNC

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestArgumentParsing:
    def test_server_is_the_default_mode(self):
        args = build_parser().parse_args([])

        assert args.mode == SERVER
        assert args.bind is None
        assert args.port is None
        assert args.data_dir is None
        assert args.run_qcluster is False

    def test_desktop_mode(self):
        assert build_parser().parse_args(['--desktop']).mode == DESKTOP

    def test_server_mode(self):
        assert build_parser().parse_args(['--server']).mode == SERVER

    def test_modes_are_mutually_exclusive(self):
        with pytest.raises(SystemExit) as exc_info:
            build_parser().parse_args(['--desktop', '--server'])

        assert exc_info.value.code == 2

    def test_address_and_data_dir_options(self):
        args = build_parser().parse_args(
            ['--bind', '10.0.0.1', '--port', '9000', '--data-dir', '/data']
        )

        assert args.bind == '10.0.0.1'
        assert args.port == 9000
        assert args.data_dir == '/data'

    def test_run_qcluster_is_accepted_but_hidden(self):
        args = build_parser().parse_args(['--run-qcluster'])

        assert args.run_qcluster is True
        assert '--run-qcluster' not in build_parser().format_help()


class TestListenAddress:
    def test_free_port_is_bindable(self):
        port = find_free_port(LOOPBACK)

        assert port_is_available(LOOPBACK, port)

    def test_desktop_picks_a_free_loopback_port(self):
        host, port = resolve_listen_address(DESKTOP, bind=None, port=None)

        assert host == LOOPBACK
        assert port_is_available(host, port)

    def test_server_defaults(self, monkeypatch):
        # Patched so the test doesn't depend on port 8000 being free here.
        monkeypatch.setattr(
            'commcare_sync.launcher.port_is_available', lambda host, port: True
        )

        host, port = resolve_listen_address(SERVER, bind=None, port=None)

        assert host == DEFAULT_SERVER_BIND
        assert port == DEFAULT_PORT

    def test_explicit_port_is_honored(self):
        wanted = find_free_port(LOOPBACK)

        host, port = resolve_listen_address(SERVER, bind=LOOPBACK, port=wanted)

        assert (host, port) == (LOOPBACK, wanted)

    def test_port_in_use_is_rejected(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
            taken.bind((LOOPBACK, 0))
            taken.listen(1)
            port = taken.getsockname()[1]

            with pytest.raises(PortUnavailableError) as exc_info:
                resolve_listen_address(SERVER, bind=LOOPBACK, port=port)

        message = str(exc_info.value)
        assert f'{LOOPBACK}:{port}' in message
        assert 'already in use' in message

    def test_desktop_port_in_use_is_rejected_too(self):
        # An explicitly requested port is never silently swapped out.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
            taken.bind((LOOPBACK, 0))
            taken.listen(1)
            port = taken.getsockname()[1]

            with pytest.raises(PortUnavailableError):
                resolve_listen_address(DESKTOP, bind=LOOPBACK, port=port)

    def test_wildcard_bind_is_reported_as_loopback(self):
        assert server_url('0.0.0.0', 8000) == 'http://127.0.0.1:8000/'

    def test_specific_bind_is_reported_as_itself(self):
        assert server_url('10.0.0.1', 8000) == 'http://10.0.0.1:8000/'


class FakeProcess:
    """Stands in for a ``subprocess.Popen`` running the task cluster."""

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


class TestClusterSupervisor:
    def make_supervisor(self, processes, **kwargs):
        """A supervisor that hands out ``processes`` in order, then reuses
        the last one for any further restart."""
        spawned = []

        def popen_factory():
            process = processes[min(len(spawned), len(processes) - 1)]
            spawned.append(process)
            return process

        kwargs.setdefault('backoff', 0)
        kwargs.setdefault('poll_interval', 0.01)
        kwargs.setdefault('stop_timeout', 0.05)
        supervisor = ClusterSupervisor(popen_factory=popen_factory, **kwargs)
        return supervisor, spawned

    def test_restarts_an_unexpected_exit(self):
        crashed = FakeProcess(pid=1, exits_with=1)
        healthy = FakeProcess(pid=2)
        supervisor, spawned = self.make_supervisor([crashed, healthy])

        supervisor.start()
        try:
            assert wait_until(lambda: spawned == [crashed, healthy])
            assert not supervisor.gave_up.is_set()
        finally:
            supervisor.stop()

    def test_gives_up_after_too_many_restarts(self):
        supervisor, spawned = self.make_supervisor(
            [FakeProcess(exits_with=1)], max_restarts=3
        )

        supervisor.start()
        try:
            assert wait_until(supervisor.gave_up.is_set)
            # The initial start plus three restarts, and no more.
            assert len(spawned) == 4
            time.sleep(0.05)
            assert len(spawned) == 4
        finally:
            supervisor.stop()

    def test_restarts_outside_the_window_do_not_count_together(self):
        supervisor, spawned = self.make_supervisor(
            [FakeProcess(exits_with=1)], max_restarts=1, restart_window=0
        )

        supervisor.start()
        try:
            # With a zero-length window every crash looks like the first one,
            # so the supervisor keeps restarting instead of giving up.
            assert wait_until(lambda: len(spawned) > 3)
            assert not supervisor.gave_up.is_set()
        finally:
            supervisor.stop()

    def test_stop_terminates_the_child(self):
        healthy = FakeProcess()
        supervisor, spawned = self.make_supervisor([healthy])

        supervisor.start()
        supervisor.stop()

        assert healthy.terminated
        assert not healthy.killed
        assert len(spawned) == 1

    def test_stop_kills_a_child_that_ignores_sigterm(self):
        stubborn = FakeProcess(hangs_on_terminate=True)
        supervisor, _spawned = self.make_supervisor([stubborn])

        supervisor.start()
        supervisor.stop()

        assert stubborn.terminated
        assert stubborn.killed


class TestRunUntilShutdown:
    def test_exits_zero_on_a_shutdown_signal(self):
        shutdown = threading.Event()
        shutdown.set()

        assert run_until_shutdown(ClusterSupervisor(), shutdown) == 0

    def test_exits_nonzero_when_the_cluster_cannot_be_kept_running(self):
        supervisor = ClusterSupervisor(
            popen_factory=lambda: FakeProcess(exits_with=1),
            max_restarts=0,
            backoff=0,
            poll_interval=0.01,
        )
        supervisor.start()
        try:
            assert run_until_shutdown(supervisor, threading.Event()) == 1
        finally:
            supervisor.stop()


class TestAlreadyRunning:
    """``main()`` bails out early when another instance is already live."""

    def test_desktop_mode_opens_browser_and_exits_zero(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            'commcare_sync.launcher.read_live_instance', lambda data_dir: 4242
        )
        opened = []
        monkeypatch.setattr(
            'commcare_sync.launcher.webbrowser.open', opened.append
        )

        exit_code = main(['--desktop', '--data-dir', str(tmp_path)])

        assert exit_code == 0
        assert opened == ['http://127.0.0.1:4242/']

    def test_server_mode_errors_and_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            'commcare_sync.launcher.read_live_instance', lambda data_dir: 4242
        )
        opened = []
        monkeypatch.setattr(
            'commcare_sync.launcher.webbrowser.open', opened.append
        )

        exit_code = main(['--server', '--data-dir', str(tmp_path)])

        assert exit_code == 1
        assert opened == []


class FakeSupervisor:
    """A ``ClusterSupervisor`` stand-in that starts and stops nothing."""

    def __init__(self, *args, **kwargs):
        self.gave_up = threading.Event()
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class TestDesktopUiRouting:
    """``main()`` shows the desktop UI only in desktop mode."""

    def patch_startup(self, monkeypatch, tmp_path):
        """Stub out everything past address resolution except the seam."""
        monkeypatch.setattr(
            'commcare_sync.launcher.bootstrap_secrets', lambda data_dir: None
        )
        monkeypatch.setattr(
            'commcare_sync.launcher.setup_django', lambda: None
        )
        monkeypatch.setattr(
            'commcare_sync.launcher.prepare_database', lambda: None
        )
        monkeypatch.setattr(
            'commcare_sync.launcher.ClusterSupervisor', FakeSupervisor
        )
        monkeypatch.setattr(
            'commcare_sync.launcher.start_web_server',
            lambda host, port: None,
        )
        monkeypatch.setattr(
            'commcare_sync.launcher.install_shutdown_handlers',
            lambda: threading.Event(),
        )

    def test_desktop_mode_calls_run_desktop_ui(self, tmp_path, monkeypatch):
        self.patch_startup(monkeypatch, tmp_path)
        calls = []
        monkeypatch.setattr(
            'commcare_sync.launcher.run_desktop_ui',
            lambda url, shutdown, request_shutdown: calls.append(url) or 0,
        )
        monkeypatch.setattr(
            'commcare_sync.launcher.run_until_shutdown',
            lambda supervisor, shutdown: pytest.fail(
                'server-mode wait used in desktop mode'
            ),
        )

        exit_code = main(['--desktop', '--data-dir', str(tmp_path)])

        assert exit_code == 0
        assert len(calls) == 1
        assert calls[0].startswith('http://127.0.0.1:')

    def test_server_mode_does_not_call_run_desktop_ui(
        self, tmp_path, monkeypatch
    ):
        self.patch_startup(monkeypatch, tmp_path)
        port = find_free_port(LOOPBACK)
        monkeypatch.setattr(
            'commcare_sync.launcher.run_desktop_ui',
            lambda url, shutdown, request_shutdown: pytest.fail(
                'run_desktop_ui used in server mode'
            ),
        )
        monkeypatch.setattr(
            'commcare_sync.launcher.run_until_shutdown',
            lambda supervisor, shutdown: 0,
        )

        exit_code = main(
            [
                '--server',
                '--data-dir',
                str(tmp_path),
                '--bind',
                LOOPBACK,
                '--port',
                str(port),
            ]
        )

        assert exit_code == 0


def launcher_command():
    """The installed ``commcare-sync`` console script, if there is one.

    Falls back to ``python -m commcare_sync.launcher``, which is the same
    entry point, so the test still runs in an environment where the project
    is on the path but not installed.
    """
    script = Path(sys.executable).with_name('commcare-sync')
    if script.exists():
        return [str(script)]
    return [sys.executable, '-m', 'commcare_sync.launcher']


def wait_for_http(url, process, timeout=60.0):
    """Return the status code of the first answered request to ``url``."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f'launcher exited with {process.returncode} before serving'
            )
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as err:
            return err.code
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    raise AssertionError(f'{url} did not answer within {timeout} seconds')


def test_server_mode_boots_serves_and_stops_cleanly(tmp_path):
    """Boot the real launcher end to end.

    The environment is deliberately minimal, so the subprocess cannot
    inherit this checkout's Django configuration: everything it needs has to
    come from ``--data-dir``. That the database lands in the data directory
    is the proof that launcher mode uses the settings overlay rather than
    ``commcare_sync/settings_local.py``.
    """
    data_dir = tmp_path / 'data'
    port = find_free_port(LOOPBACK)
    env = {
        'PATH': os.environ.get('PATH', ''),
        'HOME': str(tmp_path / 'home'),
    }
    command = launcher_command() + [
        '--server',
        '--bind',
        LOOPBACK,
        '--port',
        str(port),
        '--data-dir',
        str(data_dir),
    ]

    # Output goes to a file rather than a pipe: the task cluster child
    # inherits the launcher's stdout, so a pipe can outlive the launcher.
    output_path = tmp_path / 'launcher-output.log'
    with output_path.open('w') as output_file:
        process = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=output_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
    try:
        status = wait_for_http(f'http://{LOOPBACK}:{port}/', process)
        assert status in (200, 302)

        db_path = data_dir / 'db.sqlite3'
        assert db_path.is_file()
        with sqlite3.connect(db_path) as connection:
            schedules = connection.execute(
                'SELECT func FROM django_q_schedule WHERE func = ?',
                (DISPATCHER_FUNC,),
            ).fetchall()
        assert schedules == [(DISPATCHER_FUNC,)]

        process.send_signal(signal.SIGTERM)
        process.wait(timeout=60)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == 0, output_path.read_text()
    assert (data_dir / 'logs' / 'launcher.log').is_file()
