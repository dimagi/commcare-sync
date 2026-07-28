"""Single-instance detection via a port file in the data directory.

This module is intentionally free of Django imports, for the same reason as
its siblings: it runs before ``django.setup()``, as part of deciding whether
to start a second launcher process at all.
"""

import http.client
import json
import urllib.error
import urllib.request
from pathlib import Path

INSTANCE_FILENAME = 'instance.json'
LIVENESS_TIMEOUT = 2.0  # seconds
LOOPBACK = '127.0.0.1'


def _instance_path(data_dir: Path) -> Path:
    return data_dir / INSTANCE_FILENAME


def write_instance_file(data_dir: Path, port: int, pid: int) -> None:
    """Record the running instance's port and PID for later launches to find."""
    _instance_path(data_dir).write_text(json.dumps({'port': port, 'pid': pid}))


def remove_instance_file(data_dir: Path) -> None:
    """Remove the instance file, if it exists."""
    _instance_path(data_dir).unlink(missing_ok=True)


def read_live_instance(data_dir: Path) -> int | None:
    """Return the port of a live instance recorded in the data directory.

    A recorded instance is "live" if something answers HTTP on its port on
    loopback, regardless of status code. Anything else — no file, malformed
    contents, connection refused, timeout — means the file is stale: it is
    deleted and ``None`` is returned, so the caller can proceed to start up.
    """
    path = _instance_path(data_dir)
    try:
        port = json.loads(path.read_text())['port']
    except (OSError, ValueError, KeyError, TypeError):
        remove_instance_file(data_dir)
        return None

    # bool is a subclass of int, but a port is never a bool.
    if isinstance(port, bool) or not isinstance(port, int):
        remove_instance_file(data_dir)
        return None

    try:
        urllib.request.urlopen(
            f'http://{LOOPBACK}:{port}/', timeout=LIVENESS_TIMEOUT
        )
    except urllib.error.HTTPError:
        pass  # any HTTP response, including an error status, means "live"
    except (
        urllib.error.URLError,
        http.client.HTTPException,
        OSError,
        ValueError,
    ):
        remove_instance_file(data_dir)
        return None

    return port
