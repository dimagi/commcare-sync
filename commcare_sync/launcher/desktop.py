"""
The desktop UI: a native window on Windows and macOS, by way of
pywebview, and the default browser elsewhere.

Imported before ``django.setup()``, like ``cli``. ``webview`` is a
Windows and macOS dependency only, so it is imported where it is used.
"""

import html
import logging
import os
import sys
import threading
import webbrowser
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from commcare_sync.launcher.env import OPEN_PAGE_FILENAME

WINDOW_TITLE = 'CommCare Data Pipeline'
WEBVIEW_PLATFORMS = ('win32', 'darwin')

logger = logging.getLogger(__name__)


class WebView2Missing(Exception):
    pass


def run_desktop_ui(
    data_dir: Path,
    url: str,
    shutdown: threading.Event,
    wait_for_shutdown: Callable[[], int],
) -> int:
    """
    Shows the app and blocks until it is time to stop, returning the
    exit code. Closing the window requests shutdown, as a signal would.
    Shutdown requested another way, or ``wait_for_shutdown`` returning
    because the cluster or the web server failed, closes the window. A
    browser tab cannot be closed from here, so with the browser this
    waits as server mode does.
    """
    # One wait, however the app is shown: its result is the exit code,
    # and an exception in it reaches main() rather than a thread hook.
    with ThreadPoolExecutor(1, thread_name_prefix='window-watcher') as pool:
        waiting = pool.submit(wait_for_shutdown)
        if sys.platform in WEBVIEW_PLATFORMS:
            try:
                _show_window(url, shutdown, waiting)
            except WebView2Missing:
                logger.warning(
                    'The WebView2 runtime is not installed; '
                    'opening the browser instead'
                )
            except Exception:
                logger.warning(
                    'Could not open a desktop window; '
                    'opening the browser instead',
                    exc_info=True,
                )
            else:
                return waiting.result()
        open_in_browser(data_dir, url)
        return waiting.result()


def _show_window(
    url: str, shutdown: threading.Event, waiting: Future[int]
) -> None:
    import webview  # type: ignore[import-not-found]

    if sys.platform == 'win32':
        # Without the WebView2 runtime, pywebview falls back to Internet
        # Explorer's engine rather than failing, and the app's front end
        # does not run there. The browser does better.
        from webview.platforms.winforms import (  # type: ignore[import-not-found]
            is_chromium,
        )

        if not is_chromium:
            raise WebView2Missing
    window = webview.create_window(WINDOW_TITLE, url)

    def close_window(_: Future[int]) -> None:
        # Not yet set if the cluster or the web server failed.
        shutdown.set()
        _destroy_quietly(window)

    waiting.add_done_callback(close_window)
    logger.info('Opening the desktop window')
    # Returns when the window is closed, by the user or by close_window().
    webview.start()
    if not waiting.done():
        logger.info('The desktop window was closed; shutting down')
    shutdown.set()


def _destroy_quietly(window: Any) -> None:
    # A window the user has already closed cannot be destroyed again.
    try:
        window.destroy()
    except Exception:
        logger.debug('Could not close the desktop window', exc_info=True)


def open_in_browser(data_dir: Path, url: str) -> None:
    """
    By way of a page in the data directory, which other accounts cannot
    read, rather than as an argument: ``ps`` shows every account the
    command line of the browser, and the URL may carry the setup token.
    """
    page = data_dir / OPEN_PAGE_FILENAME
    fd = os.open(page, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as file:
        file.write(
            '<meta http-equiv="refresh" content="0; '
            f'url={html.escape(url, quote=True)}">'
        )
    webbrowser.open(page.as_uri())
