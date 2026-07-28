"""Tests for the desktop window (commcare_sync/launcher/window.py)."""

import logging
import sys
import threading

from commcare_sync.launcher.window import WINDOW_TITLE, run_desktop_ui

URL = 'http://127.0.0.1:4242/'


class FakeWebview:
    """Stands in for the ``webview`` module (pywebview)."""

    def __init__(self, start_error=None):
        self.start_error = start_error
        self.created_with = None
        self.started = False

    def create_window(self, title, url):
        self.created_with = (title, url)

    def start(self):
        self.started = True
        if self.start_error is not None:
            raise self.start_error


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

        exit_code = run_desktop_ui(URL, shutdown, requested.append)

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
            result['exit_code'] = run_desktop_ui(URL, shutdown, lambda: None)

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


class TestWebviewPath:
    """Windows/macOS: a pywebview window, faked here since this runs on Linux."""

    def test_creates_window_and_shuts_down_on_close(self, monkeypatch):
        fake = FakeWebview()
        monkeypatch.setitem(sys.modules, 'webview', fake)
        monkeypatch.setattr(sys, 'platform', 'win32')
        shutdown = threading.Event()
        requested = []

        exit_code = run_desktop_ui(URL, shutdown, lambda: requested.append(1))

        assert fake.created_with == (WINDOW_TITLE, URL)
        assert fake.started
        assert requested == [1]
        assert exit_code == 0

    def test_darwin_also_uses_webview(self, monkeypatch):
        fake = FakeWebview()
        monkeypatch.setitem(sys.modules, 'webview', fake)
        monkeypatch.setattr(sys, 'platform', 'darwin')
        shutdown = threading.Event()

        run_desktop_ui(URL, shutdown, lambda: None)

        assert fake.created_with == (WINDOW_TITLE, URL)


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
            exit_code = run_desktop_ui(URL, shutdown, requested.append)

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

        with caplog.at_level('WARNING'):
            exit_code = run_desktop_ui(URL, shutdown, lambda: None)

        assert opened == [URL]
        assert exit_code == 0
        assert 'window' in caplog.text.lower()
