"""Tests for the desktop window (commcare_sync/launcher/window.py)."""

import logging
import sys
import threading
import time

from commcare_sync.launcher.window import WINDOW_TITLE, run_desktop_ui

URL = 'http://127.0.0.1:4242/'


def wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def tracking_request_shutdown(shutdown_event, calls):
    """A ``request_shutdown`` that records each call and sets the event,
    the same way ``main()`` wires ``shutdown.set`` in for real."""

    def _request():
        calls.append(1)
        shutdown_event.set()

    return _request


class FakeWindow:
    """Stands in for the handle ``webview.create_window`` returns."""

    def __init__(self):
        self.destroyed = threading.Event()

    def destroy(self):
        self.destroyed.set()


class FakeWebview:
    """Stands in for the ``webview`` module (pywebview).

    ``start()`` blocks until the window is destroyed, matching real
    pywebview: closing the window (by the user, or by
    ``window.destroy()``) is what makes ``start()`` return.
    """

    def __init__(self, start_error=None):
        self.start_error = start_error
        self.created_with = None
        self.started = False
        self.window = FakeWindow()

    def create_window(self, title, url):
        self.created_with = (title, url)
        return self.window

    def start(self):
        self.started = True
        if self.start_error is not None:
            raise self.start_error
        self.window.destroyed.wait(timeout=5)


class TestBrowserPath:
    """The default path on this platform (Linux)."""

    def test_opens_browser_and_waits_for_shutdown(self, monkeypatch):
        opened = []
        monkeypatch.setattr(
            'commcare_sync.launcher.window.webbrowser.open', opened.append
        )
        shutdown = threading.Event()
        shutdown.set()  # already "requested", so the wait returns promptly
        requested = []

        exit_code = run_desktop_ui(
            URL, shutdown, requested.append, threading.Event()
        )

        assert opened == [URL]
        assert requested == []  # browser path never calls request_shutdown
        assert exit_code == 0

    def test_blocks_until_shutdown_is_set(self, monkeypatch):
        monkeypatch.setattr(
            'commcare_sync.launcher.window.webbrowser.open', lambda url: None
        )
        shutdown = threading.Event()
        result = {}

        def run():
            result['exit_code'] = run_desktop_ui(
                URL, shutdown, lambda: None, threading.Event()
            )

        thread = threading.Thread(target=run)
        thread.start()
        try:
            thread.join(timeout=0.2)
            assert thread.is_alive()  # still blocked, shutdown not set yet
        finally:
            shutdown.set()
            thread.join(timeout=5)
        assert not thread.is_alive()
        assert result['exit_code'] == 0

    def test_returns_one_if_the_cluster_gives_up_first(self, monkeypatch):
        monkeypatch.setattr(
            'commcare_sync.launcher.window.webbrowser.open', lambda url: None
        )
        shutdown = threading.Event()
        gave_up = threading.Event()
        gave_up.set()

        exit_code = run_desktop_ui(URL, shutdown, lambda: None, gave_up)

        assert exit_code == 1


class TestWebviewPath:
    """Windows/macOS: a pywebview window, faked here since this runs on Linux."""

    def run_in_thread(self, url, shutdown, request_shutdown, gave_up):
        result = {}

        def run():
            result['exit_code'] = run_desktop_ui(
                url, shutdown, request_shutdown, gave_up
            )

        thread = threading.Thread(target=run)
        thread.start()
        return thread, result

    def test_creates_window_and_shuts_down_on_close(self, monkeypatch):
        fake = FakeWebview()
        monkeypatch.setitem(sys.modules, 'webview', fake)
        monkeypatch.setattr(sys, 'platform', 'win32')
        shutdown = threading.Event()
        gave_up = threading.Event()
        requested = []
        request_shutdown = tracking_request_shutdown(shutdown, requested)

        thread, result = self.run_in_thread(
            URL, shutdown, request_shutdown, gave_up
        )
        try:
            assert wait_until(lambda: fake.created_with is not None)
            fake.window.destroy()  # simulate the user closing the window
        finally:
            thread.join(timeout=5)

        assert fake.created_with == (WINDOW_TITLE, URL)
        assert fake.started
        assert requested == [1]
        assert result['exit_code'] == 0
        assert not thread.is_alive()

    def test_darwin_also_uses_webview(self, monkeypatch):
        fake = FakeWebview()
        monkeypatch.setitem(sys.modules, 'webview', fake)
        monkeypatch.setattr(sys, 'platform', 'darwin')
        shutdown = threading.Event()

        thread, _result = self.run_in_thread(
            URL, shutdown, shutdown.set, threading.Event()
        )
        try:
            assert wait_until(lambda: fake.created_with is not None)
            fake.window.destroy()
        finally:
            thread.join(timeout=5)

        assert fake.created_with == (WINDOW_TITLE, URL)

    def test_gave_up_forces_the_window_closed(self, monkeypatch):
        """A cluster that gives up while the window is open still ends the
        session, the same way ``run_until_shutdown`` does for server mode:
        the watcher thread notices, requests shutdown, and destroys the
        window so ``webview.start()`` returns."""
        fake = FakeWebview()
        monkeypatch.setitem(sys.modules, 'webview', fake)
        monkeypatch.setattr(sys, 'platform', 'win32')
        shutdown = threading.Event()
        gave_up = threading.Event()
        requested = []
        request_shutdown = tracking_request_shutdown(shutdown, requested)

        thread, result = self.run_in_thread(
            URL, shutdown, request_shutdown, gave_up
        )
        try:
            assert wait_until(lambda: fake.created_with is not None)
            gave_up.set()  # the Q2 cluster child died repeatedly
        finally:
            thread.join(timeout=5)

        assert not thread.is_alive()
        assert fake.window.destroyed.is_set()
        assert requested  # request_shutdown was called at least once
        assert result['exit_code'] == 1


class TestWebviewFallback:
    """A broken pywebview install falls back to the browser, with a warning."""

    def test_start_failure_falls_back_to_browser(self, monkeypatch, caplog):
        # main() (exercised elsewhere in the suite) sets the parent
        # 'commcare_sync.launcher' logger's propagate to False; undo that
        # here so caplog (which listens on the root logger) sees records
        # from this module's child logger regardless of test order.
        monkeypatch.setattr(
            logging.getLogger('commcare_sync.launcher'), 'propagate', True
        )
        fake = FakeWebview(start_error=RuntimeError('no backend found'))
        monkeypatch.setitem(sys.modules, 'webview', fake)
        monkeypatch.setattr(sys, 'platform', 'win32')
        opened = []
        monkeypatch.setattr(
            'commcare_sync.launcher.window.webbrowser.open', opened.append
        )
        shutdown = threading.Event()
        shutdown.set()
        requested = []

        with caplog.at_level('WARNING'):
            exit_code = run_desktop_ui(
                URL, shutdown, requested.append, threading.Event()
            )

        assert fake.started
        assert opened == [URL]
        assert requested == []  # request_shutdown is not called on fallback
        assert exit_code == 0
        assert 'window' in caplog.text.lower()

    def test_missing_import_falls_back_to_browser(self, monkeypatch, caplog):
        monkeypatch.setattr(
            logging.getLogger('commcare_sync.launcher'), 'propagate', True
        )
        monkeypatch.setitem(sys.modules, 'webview', None)  # forces ImportError
        monkeypatch.setattr(sys, 'platform', 'win32')
        opened = []
        monkeypatch.setattr(
            'commcare_sync.launcher.window.webbrowser.open', opened.append
        )
        shutdown = threading.Event()
        shutdown.set()
        requested = []

        with caplog.at_level('WARNING'):
            exit_code = run_desktop_ui(
                URL, shutdown, requested.append, threading.Event()
            )

        assert opened == [URL]
        assert requested == []  # request_shutdown is not called on fallback
        assert exit_code == 0
        assert 'window' in caplog.text.lower()
