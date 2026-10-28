import logging
import os
import stat
import sys
import threading
from types import SimpleNamespace

import pytest
from unmagic import fixture, use

from commcare_sync.launcher.cli import EXIT_FAILURE
from apps.refreshes.models import RefreshConfig, RefreshRun
from commcare_sync.launcher.desktop import (
    CLOSE_CONFIRMATION,
    WINDOW_TITLE,
    confirm_close_while_runs_are_active,
    open_in_browser,
    run_desktop_ui,
)
from commcare_sync.launcher.env import OPEN_PAGE_FILENAME
from commcare_sync.tests.helpers import wait_until
from tests.fixtures import database

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
    # pywebview's Windows backend, with the WebView2 runtime present.
    fake.winforms = SimpleNamespace(is_chromium=True)
    _monkeypatch().setitem(sys.modules, 'webview.platforms', SimpleNamespace())
    _monkeypatch().setitem(
        sys.modules, 'webview.platforms.winforms', fake.winforms
    )
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

    def test_the_window_asks_before_closing_in_our_words(self):
        shutdown = threading.Event()
        thread, _ = run_in_thread(_tmp_path(), shutdown, waits_for(shutdown))
        try:
            assert wait_until(lambda: webview().started_with is not None)
        finally:
            webview().window.destroy()
            thread.join(timeout=5)

        localization = webview().started_with['localization']
        assert localization['global.quitConfirmation'] == CLOSE_CONFIRMATION
        [handler] = webview().window.events.closing.handlers
        assert handler.func is confirm_close_while_runs_are_active

    @use(_monkeypatch)
    def test_macos_also_opens_a_window(self):
        _monkeypatch().setattr(sys, 'platform', 'darwin')
        shutdown = threading.Event()
        thread, result = run_in_thread(
            _tmp_path(), shutdown, waits_for(shutdown)
        )
        try:
            assert wait_until(lambda: webview().created_with is not None)
            webview().window.destroy()
        finally:
            thread.join(timeout=5)
        assert result == [0]

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

    def test_without_the_webview2_runtime_the_browser_opens(self):
        webview().winforms.is_chromium = False
        shutdown = threading.Event()
        shutdown.set()

        with _caplog().at_level(logging.WARNING, 'commcare_sync.launcher'):
            exit_code = run_desktop_ui(
                _tmp_path(), URL, shutdown, waits_for(shutdown)
            )

        assert exit_code == 0
        assert webview().created_with is None
        assert browser() == [(_tmp_path() / OPEN_PAGE_FILENAME).as_uri()]
        assert 'WebView2 runtime is not installed' in _caplog().text
        assert 'Traceback' not in _caplog().text

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


@fixture
@use('db')
def refresh_run():
    config = RefreshConfig.objects.create(
        name='Nightly', database=database(), materialized_views=['v']
    )
    yield RefreshRun.objects.create(config=config)


@use(refresh_run)
class TestConfirmClose:
    def closing(self, status, shutdown=None):
        refresh_run().status = status
        refresh_run().save()
        window = FakeWindow()
        confirm_close_while_runs_are_active(
            window, shutdown or threading.Event()
        )
        return window.confirm_close

    def test_asks_while_a_run_is_queued(self):
        assert self.closing(RefreshRun.Status.QUEUED) is True

    def test_asks_while_a_run_is_started(self):
        assert self.closing(RefreshRun.Status.STARTED) is True

    def test_does_not_ask_when_no_run_is_active(self):
        assert self.closing(RefreshRun.Status.COMPLETED) is False

    def test_does_not_ask_once_shutdown_is_requested(self):
        # The watcher is closing the window; there is nothing to decide.
        shutdown = threading.Event()
        shutdown.set()
        assert self.closing(RefreshRun.Status.STARTED, shutdown) is False

    @use(_monkeypatch, _caplog)
    def test_asks_when_the_check_itself_fails(self):
        def fail():
            raise RuntimeError('database is locked')

        _monkeypatch().setattr('apps.schedules.tasks.runs_are_active', fail)
        with _caplog().at_level(logging.ERROR, 'commcare_sync.launcher'):
            assert self.closing(RefreshRun.Status.COMPLETED) is True
        assert 'Could not check for active runs' in _caplog().text
        assert 'database is locked' in _caplog().text
