import logging
import os
import stat
import sys
import threading

import pytest
from unmagic import fixture, use

from commcare_sync.launcher.cli import EXIT_FAILURE
from commcare_sync.launcher.desktop import (
    WINDOW_TITLE,
    open_in_browser,
    run_desktop_ui,
)
from commcare_sync.launcher.env import OPEN_PAGE_FILENAME
from commcare_sync.tests.helpers import wait_until

_tmp_path = fixture('tmp_path')
_monkeypatch = fixture('monkeypatch')
_caplog = fixture('caplog')

URL = 'http://127.0.0.1:4242/'


@use(_tmp_path, _monkeypatch)
def test_open_in_browser_hands_over_a_private_file_not_the_url():
    opened = []
    _monkeypatch().setattr('webbrowser.open', opened.append)
    url = 'http://127.0.0.1:8000/setup/?token=secret&x="y"'

    open_in_browser(_tmp_path(), url)

    page = _tmp_path() / OPEN_PAGE_FILENAME
    assert opened == [page.as_uri()]
    assert page.read_text() == (
        '<meta http-equiv="refresh" content="0; '
        'url=http://127.0.0.1:8000/setup/?token=secret&amp;x=&quot;y&quot;">'
    )
    if os.name == 'posix':
        assert stat.S_IMODE(page.stat().st_mode) == 0o600


class FakeEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


class FakeWindow:
    def __init__(self, destroy_error=None):
        self.destroy_error = destroy_error
        self.closed = threading.Event()
        self.confirm_close = False
        self.events = type('Events', (), {})()
        self.events.closing = FakeEvent()

    def destroy(self):
        self.closed.set()
        if self.destroy_error is not None:
            raise self.destroy_error


class FakeWebview:
    """
    Stands in for the ``webview`` module: ``start()`` blocks until the
    window is closed, by the user or by ``destroy()``.
    """

    def __init__(self, start_error=None):
        self.start_error = start_error
        self.created_with = None
        self.started_with = None
        self.window = FakeWindow()

    def create_window(self, title, url):
        self.created_with = (title, url)
        return self.window

    def start(self, **kwargs):
        self.started_with = kwargs
        if self.start_error is not None:
            raise self.start_error
        self.window.closed.wait(timeout=5)


def waits_for(shutdown, exit_code=0, calls=None):
    def wait():
        if calls is not None:
            calls.append(1)
        shutdown.wait(timeout=5)
        return exit_code

    return wait


def gives_up(gave_up):
    def wait():
        gave_up.wait(timeout=5)
        return EXIT_FAILURE

    return wait


@fixture
@use(_monkeypatch)
def webview():
    fake = FakeWebview()
    _monkeypatch().setitem(sys.modules, 'webview', fake)
    _monkeypatch().setattr(sys, 'platform', 'win32')
    yield fake


@fixture
@use(_monkeypatch)
def browser():
    opened = []
    _monkeypatch().setattr('webbrowser.open', opened.append)
    yield opened


def run_in_thread(data_dir, shutdown, wait):
    result = []
    thread = threading.Thread(
        target=lambda: result.append(
            run_desktop_ui(data_dir, URL, shutdown, wait)
        )
    )
    thread.start()
    return thread, result


@use(_tmp_path, browser)
class TestBrowser:
    def test_on_linux_the_browser_opens_and_the_launcher_waits(self):
        shutdown = threading.Event()
        shutdown.set()

        exit_code = run_desktop_ui(
            _tmp_path(), URL, shutdown, waits_for(shutdown)
        )

        assert exit_code == 0
        assert browser() == [(_tmp_path() / OPEN_PAGE_FILENAME).as_uri()]

    def test_the_wait_decides_the_exit_code(self):
        gave_up = threading.Event()
        gave_up.set()

        exit_code = run_desktop_ui(
            _tmp_path(), URL, threading.Event(), gives_up(gave_up)
        )

        assert exit_code == EXIT_FAILURE


@use(_tmp_path, webview, browser)
class TestWindow:
    def test_closing_the_window_requests_shutdown(self):
        shutdown = threading.Event()
        thread, result = run_in_thread(
            _tmp_path(), shutdown, waits_for(shutdown)
        )
        try:
            assert wait_until(lambda: webview().created_with is not None)
            assert not shutdown.is_set()
            webview().window.destroy()  # the user closes the window
        finally:
            thread.join(timeout=5)

        assert webview().created_with == (WINDOW_TITLE, URL)
        assert shutdown.is_set()
        assert result == [0]
        assert browser() == []

    def test_a_cluster_that_gives_up_closes_the_window(self):
        gave_up = threading.Event()
        shutdown = threading.Event()
        thread, result = run_in_thread(
            _tmp_path(), shutdown, gives_up(gave_up)
        )
        try:
            assert wait_until(lambda: webview().created_with is not None)
            gave_up.set()
        finally:
            thread.join(timeout=5)

        assert webview().window.closed.is_set()
        assert shutdown.is_set()
        assert result == [EXIT_FAILURE]

    def test_a_signal_closes_the_window(self):
        shutdown = threading.Event()
        thread, result = run_in_thread(
            _tmp_path(), shutdown, waits_for(shutdown)
        )
        try:
            assert wait_until(lambda: webview().created_with is not None)
            shutdown.set()  # what the SIGTERM handler does
        finally:
            thread.join(timeout=5)

        assert webview().window.closed.is_set()
        assert result == [0]

    def test_a_window_that_cannot_be_closed_does_not_stop_the_shutdown(
        self,
    ):
        webview().window.destroy_error = RuntimeError('already gone')
        gave_up = threading.Event()
        shutdown = threading.Event()
        thread, result = run_in_thread(
            _tmp_path(), shutdown, gives_up(gave_up)
        )
        try:
            assert wait_until(lambda: webview().created_with is not None)
            gave_up.set()
        finally:
            thread.join(timeout=5)

        assert webview().window.closed.is_set()
        assert result == [EXIT_FAILURE]

    def test_a_wait_that_fails_is_reported_not_hidden(self):
        def wait():
            raise RuntimeError('the supervisor lost its thread')

        with pytest.raises(RuntimeError, match='lost its thread'):
            run_desktop_ui(_tmp_path(), URL, threading.Event(), wait)

        assert webview().window.closed.is_set()
        assert browser() == []


@use(_tmp_path, webview, browser, _caplog)
class TestWindowFallback:
    def test_a_webview_that_cannot_start_falls_back_to_the_browser(self):
        webview().start_error = RuntimeError('no backend found')
        shutdown = threading.Event()
        shutdown.set()

        with _caplog().at_level(logging.WARNING, 'commcare_sync.launcher'):
            exit_code = run_desktop_ui(
                _tmp_path(), URL, shutdown, waits_for(shutdown)
            )

        assert exit_code == 0
        assert browser() == [(_tmp_path() / OPEN_PAGE_FILENAME).as_uri()]
        assert 'Could not open a desktop window' in _caplog().text
        assert 'no backend found' in _caplog().text

    def test_the_browser_takes_over_the_one_wait(self):
        webview().start_error = RuntimeError('no backend found')
        gave_up = threading.Event()
        calls = []

        thread, result = run_in_thread(
            _tmp_path(),
            threading.Event(),
            waits_for(gave_up, EXIT_FAILURE, calls),
        )
        try:
            assert wait_until(lambda: browser())
            gave_up.set()
        finally:
            thread.join(timeout=5)

        assert calls == [1]
        assert result == [EXIT_FAILURE]

    @use(_monkeypatch)
    def test_a_missing_webview_falls_back_to_the_browser(self):
        _monkeypatch().setitem(sys.modules, 'webview', None)
        shutdown = threading.Event()
        shutdown.set()

        with _caplog().at_level(logging.WARNING, 'commcare_sync.launcher'):
            exit_code = run_desktop_ui(
                _tmp_path(), URL, shutdown, waits_for(shutdown)
            )

        assert exit_code == 0
        assert browser() == [(_tmp_path() / OPEN_PAGE_FILENAME).as_uri()]
        assert 'Could not open a desktop window' in _caplog().text
