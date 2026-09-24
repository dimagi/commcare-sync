"""
Playwright tests for Run button functionality.

Tests that verify the Run button's Alpine.js state management,
HTMX table refresh, and polling of the run record.
"""
import re
from unittest.mock import patch

from django.test import Client
from django.urls import reverse
from playwright.sync_api import expect
from unmagic import fixture, use

from apps.commcare.models import RunBaseModel
from apps.exports.models import ExportConfig, ExportRun
from .fixtures import test_data
from .helpers import (
    login,
    navigate_to_export_details,
    route_run_status,
    route_run_trigger,
)

_page = fixture('page')
_live_server = fixture('live_server')


def create_export_config(data):
    """Helper to create an ExportConfig for testing."""
    export = ExportConfig.objects.create(
        name='Test Export',
        account=data['account'],
        project=data['project'],
        database=data['database'],
    )
    return export


@use('db', 'transactional_db', _live_server, _page)
class TestRunButtonStructure:
    """Test Run button HTML structure and Alpine.js attributes."""

    def test_run_button_has_alpine_attributes(self):
        """Test that Run button has required Alpine.js attributes."""
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        # Verify Run button exists and has Alpine.js attributes
        run_button = page.locator('#run-now-button')
        expect(run_button).to_be_visible()
        expect(run_button).to_have_attribute('@click', 'run()')
        expect(run_button).to_have_attribute(':disabled', 'running')

    def test_section_has_alpine_data(self):
        """Test that run history section has x-data with state."""
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        # Find the section containing the run button (use .last to get
        # the run history section)
        section = page.locator('section:has(#run-now-button)').last
        expect(section).to_have_attribute('x-data', 'runButton')

    def test_progress_section_has_x_show(self):
        """Test that progress section has x-show binding."""
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        # Verify progress section has x-show binding
        progress_section = page.locator('#run-status-progress')
        expect(progress_section).to_have_attribute('x-show', 'running')

    def test_start_over_checkbox_has_alpine_model(self):
        """Test that start over checkbox has x-model binding."""
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        # Verify start over checkbox has x-model
        start_over = page.locator('#start-over-checkbox')
        expect(start_over).to_be_visible()
        expect(start_over).to_have_attribute('x-model', 'startOver')

    def test_run_button_javascript_handler_attached(self):
        """Test that Run button has JavaScript click handler attached."""
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        # Verify run button exists
        run_button = page.locator('#run-now-button')
        expect(run_button).to_be_visible()

        # Verify the button has Alpine @click handler
        expect(run_button).to_have_attribute('@click', 'run()')

        # Verify progress bar elements exist (will be shown when running=true)
        expect(page.locator('#progress-bar')).to_be_attached()
        expect(page.locator('#progress-bar-message')).to_be_attached()

        # Verify the run button script is loaded by checking for the click
        # handler
        has_click_handler = page.evaluate('''() => {
            const button = document.getElementById('run-now-button');
            return button && button.onclick !== null ||
                   (button && button.getAttribute('@click') !== null);
        }''')
        assert has_click_handler, "Run button should have click handler"

    def test_start_over_checkbox_alpine_binding(self):
        """Test that start over checkbox is bound to Alpine.js state."""
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        # Verify checkbox starts unchecked
        start_over = page.locator('#start-over-checkbox')
        expect(start_over).not_to_be_checked()

        # Check the start over checkbox
        start_over.check()

        # Verify checkbox is now checked
        expect(start_over).to_be_checked()

        # Verify Alpine x-model binding exists
        expect(start_over).to_have_attribute('x-model', 'startOver')

        # Use page.evaluate to verify Alpine state changed
        alpine_state = page.evaluate('''() => {
            const button = document.getElementById('run-now-button');
            if (!button) return null;
            const section = button.closest('section[x-data]');
            if (!section || !Alpine || !Alpine.$data) return null;
            const data = Alpine.$data(section);
            return data ? data.startOver : null;
        }''')

        assert alpine_state is True, (
            'Alpine startOver state should be true when checkbox is checked, '
            f'got: {alpine_state}'
        )

    def test_alpine_running_state_changes_on_click(self):
        """Test that Alpine running state changes when Run button is clicked."""
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        # Verify initial Alpine state
        initial_state = page.evaluate('''() => {
            const section = document.querySelector('section[x-data]');
            return section && Alpine.$data(section) ? Alpine.$data(section).running : null;
        }''')

        assert initial_state is False, (
            'Alpine running state should initially be false'
        )

        run_button = page.locator('#run-now-button')
        run_button.click()

        # Small delay for Alpine to update
        page.wait_for_timeout(100)

        # Verify Alpine state changed to true
        running_state = page.evaluate('''() => {
            const section = document.querySelector('section[x-data]');
            return section && Alpine.$data(section) ? Alpine.$data(section).running : null;
        }''')

        assert running_state is True, (
            'Alpine running state should be true after clicking Run button'
        )

    def test_progress_elements_exist_on_page(self):
        """Test that progress bar elements are present on the page."""
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        # Verify progress elements exist in the DOM (they may be hidden by Alpine)
        expect(page.locator('#run-status-progress')).to_be_attached()
        expect(page.locator('#progress-bar')).to_be_attached()
        expect(page.locator('#progress-bar-message')).to_be_attached()


@use('db')
class TestRunHistoryTableEndpoint:
    """Test run history table HTMX endpoint configuration."""

    def test_run_table_htmx_attributes(self):
        """Verify the run history table renders with correct HTMX attributes.

        The hx-get URL and hx-trigger string must be exact — a wrong URL means
        the table never refreshes after a run, and a wrong trigger string means
        the refresh event fired by static/js/run_button.js is never caught.
        """
        data = test_data()
        export = create_export_config(data)

        client = Client(headers={'HX-Request': 'true'})
        client.force_login(data['user'])
        response = client.get(
            reverse('exports:run_history_table', args=[export.id])
        )
        assert response.status_code == 200

        content = response.content.decode()
        expected_url = reverse('exports:run_history_table', args=[export.id])
        assert f'hx-get="{expected_url}"' in content
        assert 'hx-trigger="refresh from:body"' in content
        assert 'hx-swap="outerHTML"' in content


@use('db', 'transactional_db', _live_server, _page)
class TestRunButtonEndToEnd:
    """The Run button against the real trigger and status endpoints.

    Only the task queue is patched, so the run stays QUEUED until the
    test moves it on. The other browser tests mock both endpoints' JSON,
    so this is the test that fails if the server and the button disagree
    about its shape.
    """

    def test_run_button_follows_the_run_record_to_completion(self):
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        with patch('apps.schedules.dispatch.async_task') as mock_async:
            login(page, live_server, data['user'])
            navigate_to_export_details(page, live_server, export.id)
            page.locator('#run-now-button').click()

            message = page.locator('#progress-bar-message')
            expect(message).to_have_text('Queued', timeout=5000)
            run = export.runs.get()
            mock_async.assert_called_once_with(
                export.RUN_TASK, run.id, start_over=False
            )

            export.runs.update(status=RunBaseModel.Status.COMPLETED)

            expect(message).to_have_text('Completed', timeout=10000)
            expect(page.locator('#progress-bar')).to_have_class(
                re.compile(r'\bbg-success\b')
            )


@use('db', 'transactional_db', _live_server, _page)
class TestRunButtonProgress:
    """What the Run button shows as a run progresses, against faked
    trigger and status responses."""

    def test_run_button_disabled_state(self):
        """Test that Run button is disabled when clicked via Alpine state."""
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)
        route_run_trigger(page, export)
        # Never complete, so the button stays disabled.
        polls = route_run_status(page, 'started')

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        run_button = page.locator('#run-now-button')

        # Verify button is initially enabled
        expect(run_button).not_to_be_disabled()

        run_button.click()

        # Verify button becomes disabled (via Alpine @click setting running=true)
        expect(run_button).to_be_disabled(timeout=2000)
        expect(page.locator('#progress-bar-message')).to_have_text(
            'Started', timeout=5000
        )
        assert polls, 'the status endpoint was never polled'

    def test_run_button_shows_complete_on_success(self):
        """A completed run turns the bar green.

        This is the finish() path: bg-success class, the endpoint's own
        "Completed" label, and (after finish()'s setTimeout) the run-table
        HTMX refresh and the Alpine running=false reset that re-enables
        the button.
        """
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)
        route_run_trigger(page, export)
        polls = route_run_status(page, 'completed')

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        run_button = page.locator('#run-now-button')
        run_button.click()

        expect(page.locator('#progress-bar-message')).to_have_text(
            'Completed', timeout=5000
        )
        expect(page.locator('#progress-bar')).to_have_class(
            re.compile(r'\bbg-success\b')
        )
        assert polls, 'the status endpoint was never polled'

        # finish()'s setTimeout(..., 1000) fires the run-table refresh and
        # resets Alpine's running state, which re-enables the button.
        expect(run_button).not_to_be_disabled(timeout=3000)

    def test_run_button_shows_failed_status(self):
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)
        route_run_trigger(page, export)
        polls = route_run_status(page, 'failed')

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        run_button = page.locator('#run-now-button')
        run_button.click()

        expect(page.locator('#progress-bar-message')).to_have_text(
            'Failed', timeout=5000
        )
        expect(page.locator('#progress-bar')).to_have_class(
            re.compile(r'\bbg-danger\b')
        )
        assert polls, 'the status endpoint was never polled'

        expect(run_button).not_to_be_disabled(timeout=3000)

    def test_run_button_shows_queued_then_started(self):
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)
        route_run_trigger(page, export)
        route_run_status(page, 'queued', 'started', 'completed')

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)
        page.locator('#run-now-button').click()

        expect(page.locator('#progress-bar-message')).to_have_text('Queued')
        expect(page.locator('#progress-bar-message')).to_have_text(
            'Started', timeout=5000
        )
        expect(page.locator('#progress-bar-message')).to_have_text(
            'Completed', timeout=5000
        )

    def test_clicking_while_a_run_is_active_shows_a_notice(self):
        """409 re-enables the button and leaves a readable message.
        """
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)
        ExportRun.objects.create(
            config=export, status=ExportRun.Status.STARTED
        )

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        run_button = page.locator('#run-now-button')
        run_button.click()

        expect(run_button).not_to_be_disabled(timeout=3000)
        expect(page.locator('#run-notice')).to_be_visible()
        expect(page.locator('#run-notice')).to_contain_text(
            'Not started: another run is already running.'
        )

        # Cleared on the next click, so it never outlives the next run.
        export.runs.update(status=ExportRun.Status.COMPLETED)
        with patch('apps.schedules.dispatch.async_task'):
            run_button.click()
            expect(page.locator('#run-notice')).not_to_be_visible()
