"""
Helpers for tests of the launcher.
"""

import socket

from commcare_sync.consts import LOOPBACK_IPV4


def listening_socket(host=LOOPBACK_IPV4):
    family = socket.AF_INET6 if ':' in host else socket.AF_INET
    taken = socket.socket(family, socket.SOCK_STREAM)
    taken.bind((host, 0))
    taken.listen(1)
    return taken
