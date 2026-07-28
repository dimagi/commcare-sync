"""Shared shutdown-wait helper for server mode and the desktop window.

Split out of ``launcher/__init__.py`` so ``launcher/window.py`` can reuse it
without importing from ``__init__.py`` (which imports ``window``) — that
would be a circular import.
"""

import threading

POLL_INTERVAL = 0.5  # seconds between checks of the give-up flag


def wait_for_shutdown(
    shutdown_event: threading.Event,
    gave_up_event: threading.Event,
    poll_interval: float = POLL_INTERVAL,
) -> int:
    """Block until shutdown is requested; return the process exit code.

    Returns 1 if ``gave_up_event`` is set before ``shutdown_event`` is —
    i.e. the Django-Q2 cluster died repeatedly and gave up rather than the
    user (or a signal) asking to stop — so a cluster that silently stops
    running exports still ends the process with a non-zero exit code
    instead of leaving a server, browser tab, or desktop window open over a
    dead background service.
    """
    while not shutdown_event.wait(poll_interval):
        if gave_up_event.is_set():
            return 1
    return 0
