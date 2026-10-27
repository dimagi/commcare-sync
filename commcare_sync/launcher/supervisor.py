"""
The Django-Q2 cluster as a supervised child process.
"""

import logging
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import psutil

from commcare_sync.launcher.processes import (
    descendants,
    stop_process_tree,
    terminate_then_kill,
)

CLUSTER_STOP_TIMEOUT = 30.0
CLUSTER_POLL_INTERVAL = 0.5

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SupervisorPolicy:
    """
    A cluster that dies repeatedly in quick succession is broken, not
    unlucky. The supervisor restarts it up to ``max_restarts`` times
    within ``restart_window`` seconds; at the next exit it gives up,
    and the exit code says so.
    """

    max_restarts: int = 3
    restart_window: float = 60.0
    backoff: float = 2.0
    stop_timeout: float = CLUSTER_STOP_TIMEOUT
    poll_interval: float = CLUSTER_POLL_INTERVAL


DEFAULT_POLICY = SupervisorPolicy()


def spawn_qcluster() -> subprocess.Popen:
    """
    A child process rather than an in-process ``Cluster()``, which
    installs its own SIGTERM and SIGINT handlers and starts
    ``multiprocessing`` children that, under the spawn start method,
    re-import the parent's main module.
    """
    if getattr(sys, 'frozen', False):
        # A PyInstaller bundle is its own executable, with no ``-m``.
        return subprocess.Popen([sys.executable, '--run-qcluster'])
    return subprocess.Popen(
        [sys.executable, '-m', 'commcare_sync.launcher', '--run-qcluster']
    )


class ClusterSupervisor:
    """
    Keeps the Django-Q2 cluster child process running. An unexpected exit
    is restarted, as far as ``policy`` allows. Past that the supervisor
    sets ``gave_up``, which the foreground loop turns into a non-zero
    exit.
    """

    def __init__(
        self,
        popen_factory: Callable[[], subprocess.Popen] = spawn_qcluster,
        stop_tree: Callable[
            [subprocess.Popen, float], None
        ] = stop_process_tree,
        policy: SupervisorPolicy = DEFAULT_POLICY,
    ):
        self._popen_factory = popen_factory
        self._stop_tree = stop_tree
        self._policy = policy
        self._process: subprocess.Popen | None = None
        # Refreshed while the child runs: if the child itself dies, its
        # workers are reparented and are no longer its descendants.
        self._descendants: list[psutil.Process] = []
        self._restarts: list[float] = []
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        # Guards the child and its descendants, so that a stop can never
        # miss a child that is being spawned at that moment, nor read a
        # descendant list that is being replaced.
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
        with self._lock:
            if self._stopping.is_set():
                return None
            process = self._popen_factory()
            self._process = process
            if self._stopping.is_set():
                self._stop_child(process)
                return None
            return process

    def _supervise(self) -> None:
        try:
            self._keep_running()
        except Exception:
            logger.exception('The task cluster supervisor failed')
            self.gave_up.set()

    def _keep_running(self) -> None:
        while not self._stopping.is_set():
            returncode = self._poll_until_exit()
            if returncode is None:
                return
            logger.warning(
                'Task cluster exited unexpectedly with code %s', returncode
            )
            self._stop_survivors()
            if not self._restart():
                return

    def _restart(self) -> bool:
        while not self._stopping.is_set():
            if not self._record_restart():
                logger.error(
                    'Task cluster exited %s times within %s seconds; giving '
                    'up. Scheduled and queued tasks will not run.',
                    self._policy.max_restarts + 1,
                    self._policy.restart_window,
                )
                self.gave_up.set()
                return False
            if self._stopping.wait(self._policy.backoff):
                return False
            try:
                process = self._spawn()
            except Exception:
                logger.exception('Could not start the task cluster')
                continue
            if process is None:
                return False
            logger.info('Restarted task cluster (pid %s)', process.pid)
            return True
        return False

    def _poll_until_exit(self) -> int | None:
        """
        Returns None when there is nothing to restart: no child, or a
        stop was requested. Keeps ``_descendants`` fresh meanwhile, for
        ``_stop_survivors()``.
        """
        process = self._process
        if process is None:
            return None
        while not self._stopping.is_set():
            # Collected before polling: an exited child has no children
            # left to list, so the list from its last moments is kept.
            found = descendants(process.pid)
            returncode = process.poll()
            if returncode is not None:
                return returncode
            with self._lock:
                self._descendants = found
            self._stopping.wait(self._policy.poll_interval)
        return None

    def _record_restart(self) -> bool:
        now = time.monotonic()
        self._restarts = [
            at
            for at in self._restarts
            if now - at < self._policy.restart_window
        ]
        if len(self._restarts) >= self._policy.max_restarts:
            return False
        self._restarts.append(now)
        return True

    def stop(self) -> None:
        self._stopping.set()
        with self._lock:
            process = self._process
            if process is not None:
                self._stop_child(process)
        if self._thread is not None:
            # The longest the thread can take to see the stop: it may be
            # terminating, then killing, the survivors of a crash, waiting
            # ``stop_timeout`` after each, before it checks again.
            policy = self._policy
            timeout = 2 * policy.stop_timeout + policy.poll_interval
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(
                    'The task cluster supervisor is still stopping '
                    'processes after %s seconds; some may be left running',
                    timeout,
                )
        self._stop_survivors()

    def _stop_survivors(self) -> None:
        with self._lock:
            found, self._descendants = self._descendants, []
        survivors = [proc for proc in found if proc.is_running()]
        if survivors:
            logger.warning(
                'Stopping %s process(es) left by the task cluster',
                len(survivors),
            )
            terminate_then_kill(survivors, self._policy.stop_timeout)

    def _stop_child(self, process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        logger.info('Stopping task cluster (pid %s)', process.pid)
        self._stop_tree(process, self._policy.stop_timeout)
