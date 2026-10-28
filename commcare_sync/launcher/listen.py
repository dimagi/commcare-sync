"""
Where the launcher listens: the address, the socket handed to waitress,
and the URL that reaches it.
"""

import errno
import socket
import sys

from commcare_sync.consts import LOOPBACK_IPV4
from commcare_sync.launcher.env import Mode

DEFAULT_PORT = 8000
DEFAULT_SERVER_BIND = '0.0.0.0'
WILDCARD_BINDS = (DEFAULT_SERVER_BIND, '::', '')


class PortUnavailableError(Exception):
    pass


def resolve_listen_address(
    mode: Mode, bind: str | None, port: int | None
) -> tuple[str, int]:
    """
    Desktop mode with no ``--port`` lets the OS pick a free port (0).
    """
    host = bind or (
        LOOPBACK_IPV4 if mode == Mode.DESKTOP else DEFAULT_SERVER_BIND
    )
    if port is None:
        port = 0 if mode == Mode.DESKTOP else DEFAULT_PORT
    return host, port


def open_listening_socket(host: str, port: int) -> socket.socket:
    """
    Bound here, once, and handed to waitress: a separate availability
    check would race with the bind, and on Windows ``SO_REUSEADDR`` lets a
    second process bind a port that another one is already listening on.
    """
    family = socket.AF_INET6 if ':' in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    if sys.platform == 'win32':
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    else:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
        sock.listen()
    except OSError as err:
        sock.close()
        if err.errno == errno.EADDRINUSE:
            reason = (
                'the address is already in use. Stop whatever is using '
                'it, or pass a different --port.'
            )
        else:
            reason = err.strerror or str(err)
        raise PortUnavailableError(
            f'Cannot listen on {url_host(host)}:{port}: {reason}'
        ) from err
    return sock


def url_host(host: str) -> str:
    """An IPv6 address is bracketed in URLs and ``Host`` headers."""
    return f'[{host}]' if ':' in host else host


def server_url(host: str, port: int) -> str:
    displayed = LOOPBACK_IPV4 if host in WILDCARD_BINDS else url_host(host)
    return f'http://{displayed}:{port}/'
