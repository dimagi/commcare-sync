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

WINDOW_TITLE = 'CommCare Data Pipeline'

# Platforms with a pywebview backend worth trying.
_WEBVIEW_PLATFORMS = ('win32', 'darwin')

logger = logging.getLogger(__name__)


def run_desktop_ui(
    url: str,
    shutdown_event: threading.Event,
    request_shutdown: Callable[[], None],
) -> int:
    """Show the app to the user, then block until it's time to shut down.

    On Windows/macOS this tries a native pywebview window first: closing it
    calls ``request_shutdown`` so the launcher tears down the cluster and
    server the same way a Ctrl-C would. If pywebview can't be imported or
    its ``start()`` call fails for any reason (no supported webview
    backend installed, etc.), that's logged as a warning and this falls
    through to the browser path below rather than crashing the launcher.

    Everywhere else — and on that fallback — the default browser is opened
    and this blocks on ``shutdown_event`` until a signal handler (or, in
    tests, a caller) sets it, just like server mode's foreground wait.
    """
    if sys.platform in _WEBVIEW_PLATFORMS:
        try:
            _run_webview(url)
        except Exception:
            logger.warning(
                'Could not open a desktop window; opening in browser instead',
                exc_info=True,
            )
        else:
            request_shutdown()
            return 0

    webbrowser.open(url)
    shutdown_event.wait()
    return 0


def _run_webview(url: str) -> None:
    """Create a pywebview window and block until it's closed.

    Imported lazily: ``webview`` is only installed on Windows and macOS,
    and this module must stay importable everywhere.
    """
    import webview  # type: ignore[import-not-found]

    webview.create_window(WINDOW_TITLE, url)
    webview.start()
