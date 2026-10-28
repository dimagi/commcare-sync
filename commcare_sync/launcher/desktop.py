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
from functools import partial
from pathlib import Path
from typing import Any

from commcare_sync.launcher.env import OPEN_PAGE_FILENAME

WINDOW_TITLE = 'CommCare Data Pipeline'
WEBVIEW_PLATFORMS = ('win32', 'darwin')
CLOSE_CONFIRMATION = (
    'A run is in progress. Closing CommCare Data Pipeline will stop it. '
    'It will start again when you next open the app.'
)

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
    window.events.closing += partial(
        confirm_close_while_runs_are_active, shutdown=shutdown
    )

    def close_window(_: Future[int]) -> None:
        # Not yet set if the cluster or the web server failed.
        shutdown.set()
        _destroy_quietly(window)

    waiting.add_done_callback(close_window)
    logger.info('Opening the desktop window')
    # Returns when the window is closed, by the user or by close_window().
    webview.start(localization={'global.quitConfirmation': CLOSE_CONFIRMATION})
    if not waiting.done():
        logger.info('The desktop window was closed; shutting down')
    shutdown.set()


def confirm_close_while_runs_are_active(
    window: Any, shutdown: threading.Event
) -> None:
    """
    Handles the window's ``closing`` event by turning pywebview's close
    confirmation on or off. pywebview reads ``confirm_close`` once the
    handlers have run; set, it asks in the words of
    ``CLOSE_CONFIRMATION``, and Cancel keeps the window open. The dialog
    is pywebview's rather than ours because on macOS this runs on the
    main thread, and ``create_confirmation_dialog`` blocks until the
    main thread shows it.
    """
    if shutdown.is_set():
        # Closed by close_window(), which fires this event too; there is
        # nothing left to decide.
        window.confirm_close = False
        return
    # Imported here: this module loads before django.setup().
    from django.db import connection

    from apps.schedules.tasks import runs_are_active

    try:
        active = runs_are_active()
    except Exception:
        # Better to ask needlessly than to stop a run without warning.
        logger.exception('Could not check for active runs before closing')
        active = True
    finally:
        # This thread's connection, which nothing else would close.
        connection.close()
    if active:
        logger.info('Asked before closing: a run is in progress')
    window.confirm_close = active


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
