"""
The ``commcare-sync`` launcher: waitress serving the app, alongside a
supervised Django-Q2 cluster child process.

This module is imported before ``django.setup()``: resolving the data
directory is what makes the settings module loadable. Everything that
needs configured settings is imported inside the function that uses it.
"""

import argparse
import logging
import multiprocessing
import os
import signal
import socket
import sys
import threading
import webbrowser
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from django.core.exceptions import ImproperlyConfigured

from commcare_sync.consts import LOCAL_BIND_ADDRESSES, LOOPBACK_IPV4
from commcare_sync.launcher.datadir import resolve_data_dir
from commcare_sync.launcher.env import (
    APP_NAME,
    DATA_DIR_ENV_VAR,
    LAUNCHER_LOG_FILENAME,
    LOG_FORMAT,
    LOGS_DIRNAME,
    MODE_ENV_VAR,
    PORT_ENV_VAR,
    Mode,
)
from commcare_sync.launcher.instance import (
    acquire_instance_lock,
    read_instance_port,
    remove_instance_file,
    write_instance_file,
)
from commcare_sync.launcher.listen import (
    DEFAULT_PORT,
    DEFAULT_SERVER_BIND,
    PortUnavailableError,
    open_listening_socket,
    resolve_listen_address,
    server_url,
)
from commcare_sync.launcher.secrets import bootstrap_secrets
from commcare_sync.launcher.supervisor import (
    CLUSTER_POLL_INTERVAL,
    ClusterSupervisor,
)

# Nothing in the data directory is for other users to read.
PRIVATE_UMASK = 0o077

# So that whatever started the launcher can tell a failure worth
# retrying from one that needs the operator: a port that cannot be
# listened on, a bad environment variable, an unreadable secrets.json
# or a broken settings.py in the data directory. Bad arguments exit
# with argparse's own code, also 2.
EXIT_FAILURE = 1
EXIT_MISCONFIGURED = 2

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description='Run CommCare Data Pipeline.',
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        '--server',
        dest='mode',
        action='store_const',
        const=Mode.SERVER,
        help='run for multiple users over the network (default)',
    )
    mode.add_argument(
        '--desktop',
        dest='mode',
        action='store_const',
        const=Mode.DESKTOP,
        help='run for a single user on this computer',
    )
    parser.set_defaults(mode=Mode.SERVER)
    parser.add_argument(
        '--bind',
        metavar='ADDR',
        help=(
            f'address to listen on (default: {DEFAULT_SERVER_BIND} in '
            f'server mode, {LOOPBACK_IPV4} in desktop mode)'
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
    # The cluster child's entry point; see supervisor.spawn_qcluster().
    parser.add_argument(
        '--run-qcluster', action='store_true', help=argparse.SUPPRESS
    )
    return parser


def start_web_server(sock: socket.socket) -> tuple[Any, threading.Thread]:
    import waitress  # type: ignore[import-untyped]

    from commcare_sync.wsgi import application

    server = waitress.create_server(
        application, sockets=[sock], ident=APP_NAME
    )
    thread = threading.Thread(target=server.run, name='waitress', daemon=True)
    thread.start()
    return server, thread


def install_shutdown_handlers() -> threading.Event:
    shutdown = threading.Event()

    def handle_signal(signum, _frame):
        logger.info('Received %s; shutting down', signal.Signals(signum).name)
        shutdown.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, handle_signal)
    return shutdown


def wait_for_shutdown(
    shutdown: threading.Event,
    supervisor: ClusterSupervisor,
    web_thread: threading.Thread,
    poll_interval: float = CLUSTER_POLL_INTERVAL,
) -> int:
    """
    Blocks until shutdown is requested, or until the cluster gave up or
    the web server died. Those two are failures, so that a half-dead
    launcher does not look healthy to whatever started it.
    """
    while not shutdown.wait(poll_interval):
        if supervisor.gave_up.is_set() or not web_thread.is_alive():
            return EXIT_FAILURE
    return 0


def configure_logging(data_dir: Path) -> None:
    """
    Only this package's logger is configured, so that it neither depends
    on nor interferes with Django's logging. No rotation: the cluster
    child writes to the same file, and rotating it from either process
    would race the other.
    """
    launcher_logger = logging.getLogger(__package__)
    for handler in list(launcher_logger.handlers):
        launcher_logger.removeHandler(handler)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            data_dir / LOGS_DIRNAME / LAUNCHER_LOG_FILENAME, encoding='utf-8'
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
    from django.core.management import call_command

    call_command('migrate', interactive=False, verbosity=0)
    # DEBUG is off, so WhiteNoise serves from STATIC_ROOT only, and nothing
    # else populates it. ``clear`` drops files left by an older version.
    call_command('collectstatic', interactive=False, verbosity=0, clear=True)

    from commcare_sync.launcher.maintenance import (
        create_admin_from_environment,
        repair_task_queue,
    )

    repair_task_queue()
    create_admin_from_environment()


def run_qcluster(data_dir_arg: str | None) -> int:
    from django.core.management import call_command

    data_dir = resolve_data_dir(data_dir_arg)
    os.environ[DATA_DIR_ENV_VAR] = str(data_dir)
    configure_logging(data_dir)
    try:
        setup_django()
        call_command('qcluster')
    except ImproperlyConfigured as err:
        logger.error('%s', err)
        return EXIT_MISCONFIGURED
    except Exception:
        # The child's stdio may go nowhere; see main().
        logger.exception('The task cluster stopped with an error')
        return EXIT_FAILURE
    return 0


def main(argv: list[str] | None = None) -> int:
    multiprocessing.freeze_support()

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.run_qcluster:
        return run_qcluster(args.data_dir)
    if (
        args.mode == Mode.DESKTOP
        and args.bind is not None
        and args.bind not in LOCAL_BIND_ADDRESSES
    ):
        # Desktop mode assumes its only client is a browser on this computer.
        parser.error(
            f'--bind must be one of {", ".join(LOCAL_BIND_ADDRESSES)} '
            'in desktop mode'
        )

    os.umask(PRIVATE_UMASK)
    data_dir = resolve_data_dir(args.data_dir)
    # For Django settings, and for the cluster child to inherit.
    os.environ[DATA_DIR_ENV_VAR] = str(data_dir)
    # commcare-export writes its log file to the working directory.
    os.chdir(data_dir)
    configure_logging(data_dir)

    try:
        lock = acquire_instance_lock(data_dir)
        if lock is None:
            return _defer_to_running_instance(data_dir, args.mode)
        # Left behind by a previous instance that was killed outright.
        remove_instance_file(data_dir)
        try:
            return _run(args, data_dir)
        finally:
            lock.close()
    except (PortUnavailableError, ImproperlyConfigured) as err:
        # For the operator; a traceback would add nothing.
        logger.error('%s', err)
        return EXIT_MISCONFIGURED
    except Exception:
        # A desktop build has no console, so the log file is the only
        # place a startup failure can be read.
        logger.exception('commcare-sync stopped with an error')
        return EXIT_FAILURE


def _defer_to_running_instance(data_dir: Path, mode: Mode) -> int:
    if mode != Mode.DESKTOP:
        logger.error('Already running (data dir %s)', data_dir)
        return EXIT_FAILURE
    port = read_instance_port(data_dir)
    if port is None:
        logger.info('Already starting up; nothing to do')
        return 0
    url = server_url(LOOPBACK_IPV4, port)
    logger.info('Already running at %s; opening browser', url)
    webbrowser.open(url)
    return 0


def _run(args: argparse.Namespace, data_dir: Path) -> int:
    bootstrap_secrets(data_dir)

    host, port = resolve_listen_address(args.mode, args.bind, args.port)
    sock = open_listening_socket(host, port)
    port = sock.getsockname()[1]

    # For Django settings, and for the cluster child to inherit.
    os.environ[MODE_ENV_VAR] = args.mode
    os.environ[PORT_ENV_VAR] = str(port)

    logger.info('Starting commcare-sync in %s mode', args.mode)
    logger.info('Using data directory %s', data_dir)
    # Each step registers its undo; the stack unwinds them in reverse.
    with ExitStack() as cleanup:
        cleanup.callback(logger.info, 'Stopped')
        cleanup.callback(sock.close)
        setup_django()
        prepare_instance()

        # Before the cluster child starts, so that a signal arriving
        # during startup stops the child instead of orphaning it.
        shutdown = install_shutdown_handlers()
        server, web_thread = start_web_server(sock)
        cleanup.callback(server.close)
        url = server_url(host, port)
        logger.info('Serving at %s', url)
        supervisor = ClusterSupervisor()
        supervisor.start()
        cleanup.callback(supervisor.stop)
        write_instance_file(data_dir, port, os.getpid())
        cleanup.callback(remove_instance_file, data_dir)
        if args.mode == Mode.DESKTOP:
            webbrowser.open(url)
        return wait_for_shutdown(shutdown, supervisor, web_thread)
