import logging
import os
import re
import signal
import sqlite3
import stat
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path

import psutil
import pytest
from django.core.exceptions import ImproperlyConfigured
from unmagic import fixture, use

from apps.schedules.maintenance import DISPATCHER_FUNC
from commcare_sync.consts import LOOPBACK_IPV4
from commcare_sync.launcher.cli import (
    EXIT_FAILURE,
    EXIT_MISCONFIGURED,
    build_parser,
    configure_logging,
    main,
    start_web_server,
    wait_for_shutdown,
)
from commcare_sync.launcher.env import (
    DATA_DIR_ENV_VAR,
    OPEN_PAGE_FILENAME,
    SETUP_TOKEN_ENV_VAR,
    Mode,
)
from commcare_sync.launcher.instance import write_cluster_file
from commcare_sync.launcher.listen import open_listening_socket
from commcare_sync.launcher.supervisor import ClusterSupervisor
from commcare_sync.tests.fixtures import launcher_process_state
from commcare_sync.tests.helpers import (
    FAST,
    FakeProcess,
    fake_stop,
    listening_socket,
    wait_until,
)
from commcare_sync.tests.test_supervisor import SLEEPER

DESKTOP = Mode.DESKTOP
SERVER = Mode.SERVER
_tmp_path = fixture('tmp_path')
_monkeypatch = fixture('monkeypatch')

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestArgumentParsing:
    def test_server_is_the_default_mode(self):
        args = build_parser().parse_args([])
        assert args.mode == SERVER
        assert args.bind is None
        assert args.port is None
        assert args.data_dir is None
        assert args.run_qcluster is False

    @pytest.mark.parametrize(
        'argv, mode', [(['--desktop'], DESKTOP), (['--server'], SERVER)]
    )
    def test_mode_flags(self, argv, mode):
        assert build_parser().parse_args(argv).mode == mode

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

    @pytest.mark.parametrize('bind', ['0.0.0.0', '10.0.0.1', '127.0.0.2'])
    def test_desktop_mode_rejects_a_bind_django_would_not_serve(self, bind):
        # Desktop mode allows the hosts in LOCAL_HOSTNAMES and no others.
        with pytest.raises(SystemExit) as exc_info:
            main(['--desktop', '--bind', bind])
        assert exc_info.value.code == 2

    @use(launcher_process_state, _tmp_path, _monkeypatch)
    @pytest.mark.parametrize('bind', ['127.0.0.1', 'localhost', '::1'])
    def test_desktop_mode_accepts_a_local_bind(self, bind):
        _monkeypatch().setattr(
            'commcare_sync.launcher.cli._run', lambda args, data_dir: 0
        )
        args = ['--desktop', '--bind', bind, '--data-dir', str(_tmp_path())]
        assert main(args) == 0

    def test_run_qcluster_is_accepted_but_hidden(self):
        args = build_parser().parse_args(['--run-qcluster'])
        assert args.run_qcluster is True
        assert '--run-qcluster' not in build_parser().format_help()


def live_thread():
    thread = threading.Thread(target=threading.Event().wait, daemon=True)
    thread.start()
    return thread


class TestWaitForShutdown:
    def test_exits_zero_on_a_shutdown_signal(self):
        shutdown = threading.Event()
        shutdown.set()
        exit_code = wait_for_shutdown(
            shutdown, ClusterSupervisor(), live_thread()
        )
        assert exit_code == 0

    def test_exits_nonzero_when_the_cluster_cannot_be_kept_running(self):
        supervisor = ClusterSupervisor(
            popen_factory=lambda: FakeProcess(exits_with=1),
            stop_tree=fake_stop,
            policy=replace(FAST, max_restarts=0),
        )
        supervisor.start()
        try:
            exit_code = wait_for_shutdown(
                threading.Event(),
                supervisor,
                live_thread(),
                poll_interval=0.01,
            )
            assert exit_code == EXIT_FAILURE
        finally:
            supervisor.stop()

    def test_exits_nonzero_when_the_web_server_dies(self):
        dead = threading.Thread(target=lambda: None)
        dead.start()
        dead.join()
        exit_code = wait_for_shutdown(
            threading.Event(), ClusterSupervisor(), dead, poll_interval=0.01
        )
        assert exit_code == EXIT_FAILURE


def test_closing_the_web_server_ends_its_thread():
    with open_listening_socket(LOOPBACK_IPV4, 0) as sock:
        server, thread = start_web_server(sock)
        assert thread.is_alive()
        server.close()
        assert wait_until(lambda: not thread.is_alive())


class IdleSupervisor(ClusterSupervisor):
    def start(self):
        pass

    def stop(self):
        pass


def desktop_args(data_dir):
    return ['--desktop', '--port', '0', '--data-dir', str(data_dir)]


@use(launcher_process_state, _tmp_path, _monkeypatch)
def test_run_det_hands_its_arguments_to_the_export_tool():
    handed = []

    def export_tool_main(argv):
        handed.append(argv)
        return 3

    _monkeypatch().setattr('commcare_export.cli.main', export_tool_main)
    _monkeypatch().setattr(
        'commcare_sync.launcher.cli.resolve_data_dir',
        lambda arg: pytest.fail('the data directory was resolved'),
    )

    exit_code = main(['--run-det', '--query', 'q.xlsx', '--version'])

    assert exit_code == 3
    # Everything after --run-det is the export tool's, including options
    # the launcher's own parser would reject.
    assert handed == [['--query', 'q.xlsx', '--version']]


@fixture
@use(_monkeypatch)
def frozen():
    _monkeypatch().setattr(sys, 'frozen', True, raising=False)
    yield


@use(launcher_process_state, _tmp_path, _monkeypatch, frozen)
class TestFrozenDefaults:
    def record_mode(self):
        modes = []

        def run(args, data_dir):
            modes.append(args.mode)
            return 0

        _monkeypatch().setattr('commcare_sync.launcher.cli._run', run)
        return modes

    def test_no_arguments_means_desktop_mode(self):
        # Double-clicked, there are no arguments and no terminal.
        _monkeypatch().setenv(DATA_DIR_ENV_VAR, str(_tmp_path()))
        modes = self.record_mode()
        assert main([]) == 0
        assert modes == [DESKTOP]

    def test_server_mode_is_still_available(self):
        modes = self.record_mode()
        assert main(['--server', '--data-dir', str(_tmp_path())]) == 0
        assert modes == [SERVER]

    def test_logs_go_to_the_data_directory_only(self):
        (_tmp_path() / 'logs').mkdir()
        configure_logging(_tmp_path())
        handlers = logging.getLogger('commcare_sync.launcher').handlers
        assert [type(handler) for handler in handlers] == [logging.FileHandler]


@use(launcher_process_state, _tmp_path, _monkeypatch)
class TestMainFailures:
    def test_port_in_use_exits_nonzero_without_booting(self):
        _monkeypatch().setattr(
            'commcare_sync.launcher.cli.setup_django',
            lambda: pytest.fail('Django was set up for a port that is taken'),
        )
        with listening_socket() as taken:
            port = taken.getsockname()[1]
            exit_code = main(
                [
                    '--bind',
                    LOOPBACK_IPV4,
                    '--port',
                    str(port),
                    '--data-dir',
                    str(_tmp_path()),
                ]
            )
        assert exit_code == EXIT_MISCONFIGURED
        log = (_tmp_path() / 'logs' / 'launcher.log').read_text()
        assert 'already in use' in log
        assert 'Traceback' not in log

    def test_a_configuration_error_is_reported_without_a_traceback(self):
        def complain(args, data_dir):
            raise ImproperlyConfigured('secrets.json is not JSON')

        _monkeypatch().setattr('commcare_sync.launcher.cli._run', complain)
        exit_code = main(['--data-dir', str(_tmp_path())])
        assert exit_code == EXIT_MISCONFIGURED
        log = (_tmp_path() / 'logs' / 'launcher.log').read_text()
        assert 'secrets.json is not JSON' in log
        assert 'Traceback' not in log

    def test_the_data_dir_is_exported_for_django_and_the_cluster_child(
        self,
    ):
        exported = []

        def record(args, data_dir):
            exported.append(os.environ[DATA_DIR_ENV_VAR])
            return 0

        _monkeypatch().setattr('commcare_sync.launcher.cli._run', record)
        assert main(['--data-dir', str(_tmp_path())]) == 0
        assert exported == [str(_tmp_path().resolve())]

    def test_a_cluster_child_failure_is_logged_before_exiting(self):
        def crash():
            raise RuntimeError('settings exploded')

        _monkeypatch().setattr(
            'commcare_sync.launcher.cli.setup_django', crash
        )
        exit_code = main(['--run-qcluster', '--data-dir', str(_tmp_path())])
        assert exit_code == EXIT_FAILURE
        log = (_tmp_path() / 'logs' / 'launcher.log').read_text()
        assert 'RuntimeError: settings exploded' in log

    @pytest.mark.skipif(sys.platform == 'win32', reason='POSIX file modes')
    def test_files_are_created_for_this_user_only(self):
        def write_something(args, data_dir):
            (data_dir / 'something').write_text('')
            return 0

        _monkeypatch().setattr(
            'commcare_sync.launcher.cli._run', write_something
        )
        assert main(['--data-dir', str(_tmp_path())]) == 0
        mode = stat.S_IMODE((_tmp_path() / 'something').stat().st_mode)
        assert mode == 0o600

    def test_a_failure_after_the_cluster_starts_stops_it(self):
        stopped = []

        class RecordingSupervisor(ClusterSupervisor):
            def start(self):
                pass

            def stop(self):
                stopped.append(self)

        def crash(data_dir, port, pid):
            raise OSError('data directory vanished')

        self.stub_the_boot(needs_setup=False)
        cli = 'commcare_sync.launcher.cli.'
        _monkeypatch().setattr(cli + 'ClusterSupervisor', RecordingSupervisor)
        _monkeypatch().setattr(cli + 'write_instance_file', crash)
        args = [
            '--bind',
            LOOPBACK_IPV4,
            '--port',
            '0',
            '--data-dir',
            str(_tmp_path()),
        ]
        assert main(args) == 1
        assert stopped

    def stub_the_boot(self, needs_setup):
        cli = 'commcare_sync.launcher.cli.'
        _monkeypatch().setattr(cli + 'setup_django', lambda: None)
        _monkeypatch().setattr(cli + 'prepare_instance', lambda: None)
        _monkeypatch().setattr(cli + 'ClusterSupervisor', IdleSupervisor)
        _monkeypatch().setattr(
            cli + 'wait_for_shutdown', lambda *args, **kwargs: 0
        )
        _monkeypatch().setattr(
            'apps.users.setup.needs_setup', lambda: needs_setup
        )

    def test_the_setup_token_reaches_django_but_not_the_cluster_child(
        self,
    ):
        seen = {}

        def setup_django():
            seen['by_django'] = os.environ[SETUP_TOKEN_ENV_VAR]

        class RecordingSupervisor(IdleSupervisor):
            def start(self):
                seen['by_child'] = os.environ.get(SETUP_TOKEN_ENV_VAR)

        self.stub_the_boot(needs_setup=True)
        cli = 'commcare_sync.launcher.cli.'
        _monkeypatch().setattr(cli + 'setup_django', setup_django)
        _monkeypatch().setattr(cli + 'ClusterSupervisor', RecordingSupervisor)
        assert main(desktop_args(_tmp_path())) == 0
        assert len(seen['by_django']) >= 32
        assert seen['by_child'] is None
        assert SETUP_TOKEN_ENV_VAR not in os.environ
        log = (_tmp_path() / 'logs' / 'launcher.log').read_text()
        assert f'/setup/?token={seen["by_django"]}' in log

    def test_desktop_mode_opens_the_setup_page_while_no_user_exists(self):
        opened = []
        self.stub_the_boot(needs_setup=True)
        _monkeypatch().setattr('webbrowser.open', opened.append)
        assert main(desktop_args(_tmp_path())) == 0
        page = _tmp_path() / OPEN_PAGE_FILENAME
        assert opened == [page.as_uri()]  # the token is not in any argv
        assert '/setup/?token=' in page.read_text()
        log = (_tmp_path() / 'logs' / 'launcher.log').read_text()
        assert 'No admin user yet' in log

    def test_desktop_mode_opens_the_home_page_once_a_user_exists(self):
        opened = []
        self.stub_the_boot(needs_setup=False)
        _monkeypatch().setattr('webbrowser.open', opened.append)
        assert main(desktop_args(_tmp_path())) == 0
        page = (_tmp_path() / OPEN_PAGE_FILENAME).read_text()
        assert f'url=http://{LOOPBACK_IPV4}:' in page
        assert 'setup' not in page
        log = (_tmp_path() / 'logs' / 'launcher.log').read_text()
        assert 'token' not in log

    def test_an_orphaned_cluster_is_stopped_before_anything_else(self):
        orphan = subprocess.Popen(SLEEPER)
        try:
            write_cluster_file(_tmp_path(), psutil.Process(orphan.pid))

            def run(args, data_dir):
                assert orphan.poll() is not None, 'the orphan is still running'
                return 0

            _monkeypatch().setattr('commcare_sync.launcher.cli._run', run)
            assert main(['--data-dir', str(_tmp_path())]) == 0
        finally:
            if orphan.poll() is None:
                orphan.kill()
        assert not (_tmp_path() / 'cluster.json').exists()

    def test_a_stale_stop_request_is_removed_at_startup(self):
        # Left by a request that arrived as the last launcher exited.
        (_tmp_path() / 'stop').touch()
        _monkeypatch().setattr(
            'commcare_sync.launcher.cli._run', lambda args, data_dir: 0
        )
        assert main(['--data-dir', str(_tmp_path())]) == 0
        assert not (_tmp_path() / 'stop').exists()

    def test_a_stale_instance_file_is_removed_at_startup(self):
        (_tmp_path() / 'instance.json').write_text('{"port": 1, "pid": 1}')
        _monkeypatch().setattr(
            'commcare_sync.launcher.cli._run', lambda args, data_dir: 0
        )
        assert main(['--data-dir', str(_tmp_path())]) == 0
        assert not (_tmp_path() / 'instance.json').exists()

    def test_a_failure_to_lock_is_logged_before_exiting(self):
        def crash(data_dir):
            raise PermissionError('instance.lock is read-only')

        _monkeypatch().setattr(
            'commcare_sync.launcher.cli.acquire_instance_lock', crash
        )
        assert main(['--data-dir', str(_tmp_path())]) == 1
        log = (_tmp_path() / 'logs' / 'launcher.log').read_text()
        assert 'instance.lock is read-only' in log

    def test_a_crash_is_logged_before_exiting(self):
        def crash(args, data_dir):
            raise RuntimeError('migrations exploded')

        _monkeypatch().setattr('commcare_sync.launcher.cli._run', crash)
        assert main(['--data-dir', str(_tmp_path())]) == 1
        log = (_tmp_path() / 'logs' / 'launcher.log').read_text()
        assert 'RuntimeError: migrations exploded' in log


def launcher_command():
    script = Path(sys.executable).with_name('commcare-sync')
    if script.exists():
        return [str(script)]
    return [sys.executable, '-m', 'commcare_sync.launcher']


def wait_for_http(url, process, timeout=60.0):
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


@use(_tmp_path)
def test_server_mode_boots_serves_and_stops_cleanly():
    # A minimal environment: everything the subprocess needs must come
    # from --data-dir, not from this checkout's settings_local.py.
    tmp_path = _tmp_path()
    data_dir = tmp_path / 'data'
    with listening_socket() as sock:
        port = sock.getsockname()[1]
    env = {'PATH': os.environ.get('PATH', ''), 'HOME': str(tmp_path / 'home')}
    command = launcher_command() + [
        '--server',
        '--bind',
        LOOPBACK_IPV4,
        '--port',
        str(port),
        '--data-dir',
        str(data_dir),
    ]
    # A file, not a pipe: the cluster child inherits stdout, and a pipe
    # could outlive the launcher.
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
        base_url = f'http://{LOOPBACK_IPV4}:{port}/'
        # Redirected to the setup page, which wants the logged token.
        assert wait_for_http(base_url, process) == 403
        # DEBUG is off, so a served stylesheet proves collectstatic ran
        # into the data dir and WhiteNoise found it there.
        css_url = f'http://{LOOPBACK_IPV4}:{port}/static/css/site.css'
        assert wait_for_http(css_url, process) == 200
        [setup_url] = re.findall(
            rf'{re.escape(base_url)}setup/\?token=\S+',
            output_path.read_text(),
        )
        assert wait_for_http(setup_url, process) == 200
        assert (data_dir / 'static_root' / 'css' / 'site.css').is_file()
        with sqlite3.connect(data_dir / 'db.sqlite3') as connection:
            schedules = connection.execute(
                'SELECT func FROM django_q_schedule WHERE func = ?',
                (DISPATCHER_FUNC,),
            ).fetchall()
        assert schedules == [(DISPATCHER_FUNC,)]
        assert (data_dir / 'instance.json').is_file()
        assert (data_dir / 'instance.lock').is_file()
        assert wait_until((data_dir / 'cluster.json').is_file)
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=60)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    assert process.returncode == 0, output_path.read_text()
    assert (data_dir / 'logs' / 'launcher.log').is_file()
    assert (data_dir / 'logs' / 'app.log').is_file()
    assert not (data_dir / 'instance.json').exists()
    assert not (data_dir / 'cluster.json').exists()


@fixture
@use(_monkeypatch)
def another_instance_holds_the_lock():
    _monkeypatch().setattr(
        'commcare_sync.launcher.cli.acquire_instance_lock',
        lambda data_dir: None,
    )
    _monkeypatch().setattr(
        'commcare_sync.launcher.cli.read_instance_port', lambda data_dir: 4242
    )
    opened = []
    _monkeypatch().setattr(
        'commcare_sync.launcher.cli.webbrowser.open', opened.append
    )
    yield opened


@use(launcher_process_state, another_instance_holds_the_lock, _tmp_path)
class TestAlreadyRunning:
    def test_desktop_mode_opens_the_running_instance(self):
        assert main(['--desktop', '--data-dir', str(_tmp_path())]) == 0
        assert another_instance_holds_the_lock() == ['http://127.0.0.1:4242/']

    def test_desktop_mode_leaves_a_starting_instance_alone(self):
        _monkeypatch().setattr(
            'commcare_sync.launcher.cli.read_instance_port',
            lambda data_dir: None,
        )
        assert main(['--desktop', '--data-dir', str(_tmp_path())]) == 0
        assert another_instance_holds_the_lock() == []

    def test_server_mode_refuses_to_start_twice(self):
        assert main(['--server', '--data-dir', str(_tmp_path())]) == 1
        assert another_instance_holds_the_lock() == []
