"""Desktop window for commcare-sync.

On Windows and macOS this opens a native window (via ``pywebview``) pointed
at the local server. On Linux — where no supported pywebview backend
exists — and as a fallback if pywebview fails for any reason, it opens the
user's default browser instead and keeps the process in the foreground
until shutdown, exactly like server mode.

This module is Django-free and must stay importable before
``django.setup()`` runs, for the same reason as its siblings in this
package: ``webview`` is imported lazily inside the function that uses it,
so its absence on Linux (it is a Windows/macOS-only dependency) never
breaks the import.
"""

import logging
import sys
import threading
import webbrowser
from collections.abc import Callable
from typing import Any

from commcare_sync.launcher.waiting import wait_for_shutdown

WINDOW_TITLE = 'CommCare Data Pipeline'

# Platforms with a pywebview backend worth trying.
_WEBVIEW_PLATFORMS = ('win32', 'darwin')

logger = logging.getLogger(__name__)


def run_desktop_ui(
    url: str,
    shutdown_event: threading.Event,
    request_shutdown: Callable[[], None],
    gave_up_event: threading.Event,
) -> int:
    """Show the app to the user, then block until it's time to shut down.

    On Windows/macOS this tries a native pywebview window first: closing it
    calls ``request_shutdown`` so the launcher tears down the cluster and
    server the same way a Ctrl-C would. A background watcher thread also
    force-closes the window if ``gave_up_event`` is set (the Q2 cluster
    child died repeatedly and gave up) or if shutdown is requested some
    other way while the window is open — Ctrl-C is not expected to reach a
    native window, only the browser fallback below, so this is what makes
    a signal or a permanently-dead cluster still end a desktop session. If
    pywebview can't be imported or its ``start()`` call fails for any
    reason (no supported webview backend installed, etc.), that's logged
    as a warning and this falls through to the browser path instead of
    crashing the launcher.

    Everywhere else — and on that fallback — the default browser is opened
    and this blocks until a signal handler (or, in tests, a caller) sets
    ``shutdown_event``, just like server mode's foreground wait; it
    likewise returns 1 if the cluster gives up first.
    """
    if sys.platform in _WEBVIEW_PLATFORMS:
        try:
            _run_webview(url, shutdown_event, gave_up_event, request_shutdown)
        except Exception:
            logger.warning(
                'Could not open a desktop window; opening in browser instead',
                exc_info=True,
            )
        else:
            request_shutdown()
            return 1 if gave_up_event.is_set() else 0

    webbrowser.open(url)
    return wait_for_shutdown(shutdown_event, gave_up_event)


def _run_webview(
    url: str,
    shutdown_event: threading.Event,
    gave_up_event: threading.Event,
    request_shutdown: Callable[[], None],
) -> None:
    """Create a pywebview window and block until it's closed.

    Imported lazily: ``webview`` is only installed on Windows and macOS,
    and this module must stay importable everywhere.
    """
    import webview  # type: ignore[import-not-found]

    window = webview.create_window(WINDOW_TITLE, url)
    watcher = threading.Thread(
        target=_watch_for_shutdown,
        args=(window, shutdown_event, gave_up_event, request_shutdown),
        name='desktop-window-watcher',
        daemon=True,
    )
    watcher.start()
    webview.start()


def _watch_for_shutdown(
    window: Any,
    shutdown_event: threading.Event,
    gave_up_event: threading.Event,
    request_shutdown: Callable[[], None],
) -> None:
    """Force the window closed if shutdown is needed while it's still open.

    Runs alongside ``webview.start()`` in a daemon thread. If the cluster
    gives up, this requests shutdown itself (nothing else would, since the
    user hasn't closed the window); either way, once shutdown is underway
    it destroys the window so ``webview.start()`` returns and the launcher
    can finish tearing down.

    Inert on a normal close: by the time the user closes the window
    themselves, ``webview.start()`` has already returned and this thread's
    ``window.destroy()`` call — reached a moment later, once
    ``request_shutdown()`` in the caller sets ``shutdown_event`` — is a
    harmless no-op on an already-closed window.
    """
    if wait_for_shutdown(shutdown_event, gave_up_event) == 1:
        request_shutdown()
    _destroy_quietly(window)


def _destroy_quietly(window: Any) -> None:
    try:
        window.destroy()
    except Exception:
        logger.debug(
            'Could not destroy the desktop window (likely already closed)',
            exc_info=True,
        )
