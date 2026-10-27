"""
Single-instance detection. The running launcher holds an exclusive lock
on a file in the data directory for its whole lifetime, so a second
launcher can tell at once, even during the first one's startup. The OS
releases the lock when the process dies, however it dies. A second file
names the port, for the second launcher to open in the browser.

The cluster child holds no lock and outlives a launcher that is killed
outright, so it records itself in a third file, for the next launcher to
stop it before touching the database.

Runs before ``django.setup()``.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import IO

import psutil

INSTANCE_FILENAME = 'instance.json'
LOCK_FILENAME = 'instance.lock'
CLUSTER_FILENAME = 'cluster.json'

logger = logging.getLogger(__name__)


def acquire_instance_lock(data_dir: Path) -> IO | None:
    """
    Returns the open lock file to hold until exit, or ``None`` if another
    launcher holds it.
    """
    lock_file = (data_dir / LOCK_FILENAME).open('a+')
    try:
        _lock_exclusively(lock_file)
    except OSError:
        lock_file.close()
        return None
    return lock_file


if sys.platform == 'win32':
    import msvcrt

    def _lock_exclusively(lock_file: IO) -> None:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)

else:
    import fcntl

    def _lock_exclusively(lock_file: IO) -> None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def write_instance_file(data_dir: Path, port: int, pid: int) -> None:
    _write_json(data_dir / INSTANCE_FILENAME, {'port': port, 'pid': pid})


def remove_instance_file(data_dir: Path) -> None:
    (data_dir / INSTANCE_FILENAME).unlink(missing_ok=True)


def read_instance_port(data_dir: Path) -> int | None:
    path = data_dir / INSTANCE_FILENAME
    record = _read_json(path)
    if record is None:
        return None
    port = record.get('port')
    if isinstance(port, bool) or not isinstance(port, int):
        logger.warning('Ignoring %s: it names no port', path)
        return None
    return port


def write_cluster_file(data_dir: Path, process: psutil.Process) -> None:
    _write_json(
        data_dir / CLUSTER_FILENAME,
        {'pid': process.pid, 'create_time': process.create_time()},
    )


def remove_cluster_file(data_dir: Path) -> None:
    (data_dir / CLUSTER_FILENAME).unlink(missing_ok=True)


def read_cluster_process(data_dir: Path) -> psutil.Process | None:
    """
    The recorded cluster child, if it is still running. The creation
    time tells it apart from an unrelated process that reused its pid.
    """
    path = data_dir / CLUSTER_FILENAME
    record = _read_json(path)
    if record is None:
        return None
    try:
        process = psutil.Process(record['pid'])
        if process.create_time() == record['create_time']:
            return process
    except (KeyError, TypeError, ValueError):
        logger.warning('Ignoring %s: it names no process', path)
    except psutil.NoSuchProcess:
        pass
    except psutil.Error as err:
        logger.warning('Ignoring the process recorded in %s: %s', path, err)
    return None


def _write_json(path: Path, record: dict) -> None:
    """Replaced whole, so that a reader never sees a partial file."""
    temp_path = path.with_name(path.name + '.tmp')
    try:
        temp_path.write_text(json.dumps(record))
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _read_json(path: Path) -> dict | None:
    """``None`` for a missing file, and for an unusable one, which is logged."""
    try:
        record = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as err:
        logger.warning('Ignoring %s: %s', path, err)
        return None
    if not isinstance(record, dict):
        logger.warning('Ignoring %s: not a JSON object', path)
        return None
    return record
