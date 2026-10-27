"""
Stopping a process together with its descendants. On Windows
``terminate()`` kills only the named process, so the Django-Q2 workers,
and any commcare-export they started, would survive it.
"""

import logging
import subprocess
from collections.abc import Callable

import psutil

logger = logging.getLogger(__name__)


def descendants(pid: int) -> list[psutil.Process]:
    """Every process under ``pid``; none if it has already gone."""
    try:
        return psutil.Process(pid).children(recursive=True)
    except psutil.NoSuchProcess:
        return []


def stop_process_tree(process: subprocess.Popen, timeout: float) -> None:
    """Stops a child process and everything under it, and reaps it."""
    try:
        root = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        root = None  # exited and reaped already
    else:
        terminate_then_kill([root, *descendants(process.pid)], timeout)
    process.wait()


def terminate_then_kill(
    processes: list[psutil.Process], timeout: float
) -> list[psutil.Process]:
    """Returns whatever survives both, which should be nothing."""
    _stop_each(processes, lambda proc: proc.terminate())
    _, alive = psutil.wait_procs(processes, timeout=timeout)
    if alive:
        logger.warning(
            'Processes %s did not stop within %s seconds; killing them',
            [proc.pid for proc in alive],
            timeout,
        )
        _stop_each(alive, lambda proc: proc.kill())
        _, alive = psutil.wait_procs(alive, timeout=timeout)
        if alive:
            logger.error(
                'Processes %s survived being killed',
                [proc.pid for proc in alive],
            )
    return alive


def _stop_each(
    processes: list[psutil.Process], stop: Callable[[psutil.Process], None]
) -> None:
    for proc in processes:
        try:
            stop(proc)
        except psutil.NoSuchProcess:
            pass  # gone already, as intended
        except psutil.Error as err:
            logger.warning('Could not stop pid %s: %s', proc.pid, err)
