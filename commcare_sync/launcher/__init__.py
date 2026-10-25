"""Desktop/server launcher for commcare-sync.

``main()`` is the ``commcare-sync`` console script: it resolves the data
directory, boots Django, brings the database and collected static files up to
date, repairs whatever a previous process left behind, then runs the web
server (waitress) with a
supervised Django-Q2 cluster child process alongside it until a shutdown
signal arrives.

This module must stay importable before ``django.setup()`` runs, because
resolving the data directory is what makes the settings module loadable in
the first place. Everything that needs configured settings — waitress, the
WSGI app, the maintenance helpers — is therefore imported inside functions.
"""

import argparse
import logging
import multiprocessing
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path

from commcare_sync.launcher.datadir import resolve_data_dir
from commcare_sync.launcher.instance import (
    read_live_instance,
    remove_instance_file,
    write_instance_file,
)
from commcare_sync.launcher.secrets import bootstrap_secrets
from commcare_sync.launcher.waiting import wait_for_shutdown
from commcare_sync.launcher.window import run_desktop_ui

DESKTOP = 'desktop'
SERVER = 'server'

DEFAULT_PORT = 8000
# A server install listens on every interface; a desktop one stays local.
DEFAULT_SERVER_BIND = '0.0.0.0'
LOOPBACK = '127.0.0.1'
# Binds that mean "every interface", and so name no host to link to.
WILDCARD_BINDS = ('0.0.0.0', '', '*')

LOG_FILENAME = 'launcher.log'
LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'

# Cluster supervision: a cluster that dies repeatedly in quick succession is
# broken rather than unlucky, so stop restarting it and let the exit code
# tell the operator (or systemd) about it.
MAX_CLUSTER_RESTARTS = 3
CLUSTER_RESTART_WINDOW = 60.0  # seconds
CLUSTER_RESTART_BACKOFF = 2.0  # seconds
CLUSTER_STOP_TIMEOUT = 30.0  # seconds to wait for SIGTERM before SIGKILL
CLUSTER_POLL_INTERVAL = 0.5  # seconds between child liveness checks

logger = logging.getLogger(__name__)


class PortUnavailableError(Exception):
    """The requested listening address is already taken."""


# --- CLI ------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='commcare-sync',
        description='Run CommCare Data Pipeline.',
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        '--server',
        dest='mode',
        action='store_const',
        const=SERVER,
        help='run headless for multiple users over the network (default)',
    )
    mode.add_argument(
        '--desktop',
        dest='mode',
        action='store_const',
        const=DESKTOP,
        help='run for a single user on this computer',
    )
    parser.set_defaults(mode=SERVER)
    parser.add_argument(
        '--bind',
        metavar='ADDR',
        help=(
            f'address to listen on (default: {DEFAULT_SERVER_BIND} in server '
            f'mode, {LOOPBACK} in desktop mode)'
        ),
    )
    parser.add_argument(
        '--port',
        type=int,
        metavar='N',
        help=(
            f'port to listen on (default: {DEFAULT_PORT} in server mode, '
            'a free port in desktop mode)'
        ),
    )
    parser.add_argument(
        '--data-dir',
        metavar='PATH',
        help=(
            'directory holding the database, secrets, logs and media '
            '(default: the per-user data directory for this platform)'
        ),
    )
    # Hidden: how the launcher runs its own task cluster child process.
    parser.add_argument(
        '--run-qcluster', action='store_true', help=argparse.SUPPRESS
    )
    return parser


# --- Listening address ----------------------------------------------------


def find_free_port(host: str) -> int:
    """Return a port nothing is listening on, by letting the OS pick one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def port_is_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
        return True


def resolve_listen_address(
    mode: str, bind: str | None, port: int | None
) -> tuple[str, int]:
    """Decide what address to serve on, per mode.

    Desktop mode with no explicit ``--port`` picks a free port, because a
    single-user install has no reason to care which one it gets. Any
    explicitly requested port — and server mode's default — must be free,
    and fails fast if it isn't.
    """
    host = bind or (LOOPBACK if mode == DESKTOP else DEFAULT_SERVER_BIND)
    if port is None and mode == DESKTOP:
        return host, find_free_port(host)
    wanted = DEFAULT_PORT if port is None else port
    if not port_is_available(host, wanted):
        raise PortUnavailableError(
            f'Cannot listen on {host}:{wanted}: the address is already in '
            'use. Stop whatever is using it, or pass a different --port.'
        )
    return host, wanted


def server_url(host: str, port: int) -> str:
    """The URL to tell the user about for a server bound to ``host:port``."""
    displayed = LOOPBACK if host in WILDCARD_BINDS else host
    return f'http://{displayed}:{port}/'


# --- Task cluster ---------------------------------------------------------


def spawn_qcluster() -> subprocess.Popen:
    """Start the Django-Q2 cluster as a child of this process.

    A child process rather than an in-process ``Cluster()``: django-q2 uses
    ``multiprocessing`` internally, and keeping that in a separate process
    isolates the launcher from its startup and shutdown quirks (and from
    ``spawn`` semantics on Windows and in a frozen build).
    """
    if getattr(sys, 'frozen', False):
        # SPIKE: the bundle has no `-m`; sys.executable is the bundle itself.
        return subprocess.Popen([sys.executable, '--run-qcluster'])
    return subprocess.Popen(
        [sys.executable, '-m', 'commcare_sync.launcher', '--run-qcluster'],
    )


class ClusterSupervisor:
    """Keeps the Django-Q2 cluster child process running.

    A background thread watches the child. An unexpected exit is restarted,
    up to ``max_restarts`` times within ``restart_window`` seconds; past
    that the supervisor gives up and sets :attr:`gave_up`, which the
    foreground loop turns into a non-zero exit.
    """

    def __init__(
        self,
        popen_factory: Callable[[], subprocess.Popen] = spawn_qcluster,
        max_restarts: int = MAX_CLUSTER_RESTARTS,
        restart_window: float = CLUSTER_RESTART_WINDOW,
        backoff: float = CLUSTER_RESTART_BACKOFF,
        stop_timeout: float = CLUSTER_STOP_TIMEOUT,
        poll_interval: float = CLUSTER_POLL_INTERVAL,
    ):
        self._popen_factory = popen_factory
        self._max_restarts = max_restarts
        self._restart_window = restart_window
        self._backoff = backoff
        self._stop_timeout = stop_timeout
        self._poll_interval = poll_interval

        self._process: subprocess.Popen | None = None
        self._restarts: list[float] = []
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        # Serializes spawning against stopping, so a stop can never miss a
        # child that is being spawned at that moment.
        self._lock = threading.Lock()
        self.gave_up = threading.Event()

    def start(self) -> None:
        process = self._spawn()
        if process is not None:
            logger.info('Started task cluster (pid %s)', process.pid)
        self._thread = threading.Thread(
            target=self._supervise, name='cluster-supervisor', daemon=True
        )
        self._thread.start()

    def _spawn(self) -> subprocess.Popen | None:
        """Start a cluster child, or nothing if a stop is underway.

        Both the lock and the re-check after the factory returns are needed
        to close the window between spawning a child and :attr:`_process`
        naming it: a ``stop()`` landing in that window would otherwise
        terminate the child this one replaced and leave this one orphaned,
        still running against the database after shutdown.
        """
        with self._lock:
            if self._stopping.is_set():
                return None
            process = self._popen_factory()
            self._process = process
            if self._stopping.is_set():
                self._terminate(process)
                return None
            return process

    def _supervise(self) -> None:
        while not self._stopping.is_set():
            returncode = self._wait_for_exit()
            if returncode is None:  # we are shutting down; not a crash
                return
            logger.warning(
                'Task cluster exited unexpectedly with code %s', returncode
            )
            if not self._record_restart():
                logger.error(
                    'Task cluster exited %s times within %s seconds; giving '
                    'up. Scheduled and queued tasks will not run.',
                    self._max_restarts + 1,
                    self._restart_window,
                )
                self.gave_up.set()
                return
            if self._stopping.wait(self._backoff):
                return
            process = self._spawn()
            if process is None:  # a stop beat the restart to it
                return
            logger.info('Restarted task cluster (pid %s)', process.pid)

    def _wait_for_exit(self) -> int | None:
        """Block until the child exits, or ``None`` if we're stopping."""
        process = self._process
        if process is None:  # never spawned, because we are stopping
            return None
        while not self._stopping.is_set():
            returncode = process.poll()
            if returncode is not None:
                return returncode
            self._stopping.wait(self._poll_interval)
        return None

    def _record_restart(self) -> bool:
        """Note a restart, or return False if we've had too many too fast."""
        now = time.monotonic()
        self._restarts = [
            at for at in self._restarts if now - at < self._restart_window
        ]
        if len(self._restarts) >= self._max_restarts:
            return False
        self._restarts.append(now)
        return True

    def stop(self) -> None:
        """Stop supervising and shut the child down, SIGKILLing if it hangs."""
        self._stopping.set()
        with self._lock:
            process = self._process
            if process is not None:
                self._terminate(process)
        if self._thread is not None:
            self._thread.join(timeout=self._poll_interval * 4)

    def _terminate(self, process: subprocess.Popen) -> None:
        """Terminate the child and all its descendants, killing stragglers.

        SPIKE: on Windows ``terminate()`` kills only the named process, so
        the Django-Q2 workers (and any commcare-export they started) would
        survive it. Collect the whole tree first, then terminate, wait, and
        kill whatever is left.
        """
        if process.poll() is not None:
            return
        import psutil

        logger.info('Stopping task cluster (pid %s)', process.pid)
        try:
            parent = psutil.Process(process.pid)
            tree = parent.children(recursive=True) + [parent]
        except psutil.NoSuchProcess:
            return
        logger.info('Process tree to stop: %s', [p.pid for p in tree])
        for proc in tree:
            try:
                proc.terminate()
            except psutil.NoSuchProcess:
                pass
        _gone, alive = psutil.wait_procs(tree, timeout=self._stop_timeout)
        if alive:
            logger.warning(
                'Processes %s did not stop within %s seconds; killing them',
                [p.pid for p in alive],
                self._stop_timeout,
            )
            for proc in alive:
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
            psutil.wait_procs(alive, timeout=10)
        process.wait()


# --- Web server -----------------------------------------------------------


def start_web_server(host: str, port: int) -> threading.Thread:
    """Serve the Django app with waitress in a daemon thread.

    The listening socket is opened here rather than in the thread, so a
    failure to bind raises where the caller can report it instead of
    quietly killing the thread and leaving a server that answers nothing.
    """
    import waitress  # type: ignore[import-untyped]

    from commcare_sync.wsgi import application

    server = waitress.create_server(
        application, host=host, port=port, ident='commcare-sync'
    )
    thread = threading.Thread(target=server.run, name='waitress', daemon=True)
    thread.start()
    return thread


# --- Foreground -----------------------------------------------------------


def install_shutdown_handlers() -> threading.Event:
    """Return an event that SIGTERM and SIGINT set.

    Installed before the cluster child starts: a signal arriving during
    startup then runs the shutdown path instead of killing this process and
    orphaning the child.
    """
    shutdown = threading.Event()

    def handle_signal(signum, _frame):
        logger.info('Received %s; shutting down', signal.Signals(signum).name)
        shutdown.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, handle_signal)

    return shutdown


def run_until_shutdown(
    supervisor: ClusterSupervisor, shutdown: threading.Event
) -> int:
    """Block until ``shutdown`` is set, and return the process exit code.

    This is the seam desktop mode's window sits in instead: the window
    runs its own event loop in the foreground, and closing it (or the
    cluster giving up) ends the wait the same way.
    """
    return wait_for_shutdown(
        shutdown, supervisor.gave_up, CLUSTER_POLL_INTERVAL
    )


# --- Startup --------------------------------------------------------------


def configure_logging(data_dir: Path) -> None:
    """Log launcher events to stdout and ``<data-dir>/logs/launcher.log``.

    Only this package's logger is configured, so it neither depends on nor
    interferes with Django's own logging setup.
    """
    launcher_logger = logging.getLogger(__name__)
    for handler in list(launcher_logger.handlers):
        launcher_logger.removeHandler(handler)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            data_dir / 'logs' / LOG_FILENAME, encoding='utf-8'
        ),
    ]
    formatter = logging.Formatter(LOG_FORMAT)
    for handler in handlers:
        handler.setFormatter(formatter)
        launcher_logger.addHandler(handler)
    launcher_logger.setLevel(logging.INFO)
    launcher_logger.propagate = False


def setup_django() -> None:
    import django

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'commcare_sync.settings')
    django.setup()


def prepare_instance() -> None:
    """Migrate, collect static files, then repair what a previous run left."""
    from django.core.management import call_command

    call_command('migrate', interactive=False, verbosity=0)

    # Launcher mode runs with DEBUG=False, so WhiteNoise serves static files
    # from STATIC_ROOT only — nothing else populates it, and an unstyled app
    # is the result if this doesn't run. `clear` keeps a stale STATIC_ROOT
    # from an older version out of the way after an upgrade.
    call_command('collectstatic', interactive=False, verbosity=0, clear=True)

    # Imported here, not at module level: it touches Django models.
    from commcare_sync.launcher import maintenance

    maintenance.ensure_dispatcher_schedule()
    maintenance.clear_stale_queue_locks()
    maintenance.reap_stale_runs()
    maintenance.ensure_admin_user()


def run_qcluster() -> int:
    """Run the Django-Q2 cluster in this process (the ``--run-qcluster`` child).

    The parent passes everything through the environment, so this only has
    to rediscover the data directory and boot Django.
    """
    from django.core.management import call_command

    resolve_data_dir()
    setup_django()
    call_command('qcluster')
    return 0


def run_det(det_argv: list[str]) -> int:
    """SPIKE: ``--run-det``, the bundle acting as commcare-export."""
    from commcare_export.cli import main as det_main

    det_main(det_argv)  # calls sys.exit() itself
    return 0


def spike_imports() -> int:
    """SPIKE: import every SQL driver the extras bring, report versions."""
    import importlib

    failed = 0
    for name in (
        'psycopg',
        'psycopg2',
        'pymysql',
        'pyodbc',
        'sqlalchemy',
        'alembic',
        'anymail',
        'django_q',
        'commcare_export',
        'whitenoise',
        'waitress',
        'platformdirs',
        'psutil',
        'webview',
    ):
        try:
            module = importlib.import_module(name)
        except Exception as err:  # noqa: BLE001
            failed += 1
            print(f'IMPORT FAIL {name}: {err!r}')
        else:
            version = getattr(module, '__version__', getattr(module, 'version', '?'))
            print(f'IMPORT OK   {name} {version}')
    return 1 if failed else 0


def watch_stop_file(data_dir: Path, shutdown: threading.Event) -> None:
    """SPIKE: set ``shutdown`` when ``<data-dir>/STOP`` appears.

    Lets the smoke test drive the launcher's own shutdown path on every
    platform. Windows has no SIGTERM to send to a console process.
    """
    stop_file = data_dir / 'STOP'

    def watch():
        while not shutdown.is_set():
            if stop_file.exists():
                logger.info('STOP file found; shutting down')
                shutdown.set()
                return
            time.sleep(0.5)

    threading.Thread(target=watch, name='stop-file', daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    multiprocessing.freeze_support()

    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ['--run-det']:
        return run_det(argv[1:])
    if argv[:1] == ['--spike-imports']:
        return spike_imports()

    args = build_parser().parse_args(argv)
    if args.run_qcluster:
        return run_qcluster()

    data_dir = resolve_data_dir(args.data_dir)
    configure_logging(data_dir)
    logger.info('sys.frozen=%s executable=%s', getattr(sys, 'frozen', False), sys.executable)

    live_port = read_live_instance(data_dir)
    if live_port is not None:
        url = server_url(LOOPBACK, live_port)
        if args.mode == DESKTOP:
            logger.info('Already running at %s; opening browser', url)
            webbrowser.open(url)
            return 0
        logger.error('Already running at %s (data dir %s)', url, data_dir)
        return 1

    bootstrap_secrets(data_dir)

    try:
        host, port = resolve_listen_address(args.mode, args.bind, args.port)
    except PortUnavailableError as err:
        logger.error('%s', err)
        return 1

    os.environ['COMMCARE_SYNC_MODE'] = args.mode
    os.environ['COMMCARE_SYNC_PORT'] = str(port)

    logger.info('Starting commcare-sync in %s mode', args.mode)
    logger.info('Using data directory %s', data_dir)
    setup_django()
    prepare_instance()

    shutdown = install_shutdown_handlers()
    watch_stop_file(data_dir, shutdown)
    supervisor = ClusterSupervisor()
    supervisor.start()
    try:
        start_web_server(host, port)
        url = server_url(host, port)
        logger.info('Serving at %s', url)
        write_instance_file(data_dir, port, os.getpid())
        try:
            if args.mode == DESKTOP:
                return run_desktop_ui(
                    url, shutdown, shutdown.set, supervisor.gave_up
                )
            return run_until_shutdown(supervisor, shutdown)
        finally:
            remove_instance_file(data_dir)
    except OSError as err:
        logger.error('Cannot listen on %s:%s: %s', host, port, err)
        return 1
    finally:
        supervisor.stop()
        logger.info('Stopped')
