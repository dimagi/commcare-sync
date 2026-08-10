"""
Playwright tests for Run button functionality.

Tests that verify the Run button's Alpine.js state management,
HTMX table refresh, and integration with background task-status polling.
"""
import json
import re

from django.test import Client
from django.urls import reverse
from playwright.sync_api import expect
from unmagic import fixture, use

from apps.exports.models import ExportConfig
from .fixtures import test_data
from .helpers import login, navigate_to_export_details

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
        expect(run_button).to_have_attribute(
            '@click', "running = true; notice = ''"
        )
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
        expect(section).to_have_attribute(
            'x-data',
            "{ running: false, startOver: false, notice: '' }"
        )

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


@use('db')
class TestRunHistoryTableEndpoint:
    """Test run history table HTMX endpoint configuration."""

    def test_run_table_htmx_attributes(self):
        """Verify the run history table renders with correct HTMX attributes.

        The hx-get URL and hx-trigger string must be exact — a wrong URL means
        the table never refreshes after a run, and a wrong trigger string means
        the refresh event fired by run_button_script.html is never caught.
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
class TestRunButtonWithMocks:
    """Test Run button functionality with mocked API responses."""

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
        expect(run_button).to_have_attribute(
            '@click', "running = true; notice = ''"
        )

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

    def test_run_button_disabled_state(self):
        """Test that Run button is disabled when clicked via Alpine state."""
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        def mock_run_export(route):
            route.fulfill(
                status=200,
                content_type='application/json',
                body=json.dumps({
                    'run_id': 1,
                    'poll_url': '/exports/runs/1/status/',
                }),
            )

        hits = []

        def mock_run_status(route):
            # Never complete, so the button stays disabled.
            hits.append(route.request.url)
            route.fulfill(
                status=200,
                content_type='application/json',
                body=json.dumps({
                    'status': 'started',
                    'label': 'Started',
                    'complete': False,
                }),
            )

        page.route(f'**/exports/api/run/{export.id}/**', mock_run_export)
        page.route('**/runs/**/status/', mock_run_status)

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
        assert hits, 'the status endpoint was never polled'

    def test_run_button_shows_complete_on_success(self):
        """Test the poll() 'complete: true' branch for a completed run.

        This is the finish() path: bg-success class, the endpoint's own
        "Completed" label, and (after finish()'s setTimeout) the run-table
        HTMX refresh and the Alpine running=false reset that re-enables
        the button.
        """
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        def mock_run_export(route):
            route.fulfill(
                status=200,
                content_type='application/json',
                body=json.dumps({
                    'run_id': 1,
                    'poll_url': '/exports/runs/1/status/',
                }),
            )

        hits = []

        def mock_run_status(route):
            hits.append(route.request.url)
            route.fulfill(
                status=200,
                content_type='application/json',
                body=json.dumps({
                    'status': 'completed',
                    'label': 'Completed',
                    'complete': True,
                }),
            )

        page.route(f'**/exports/api/run/{export.id}/**', mock_run_export)
        page.route('**/runs/**/status/', mock_run_status)

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
        assert hits, 'the status endpoint was never polled'

        # finish()'s setTimeout(..., 1000) fires the run-table refresh and
        # resets Alpine's running state, which re-enables the button.
        expect(run_button).not_to_be_disabled(timeout=3000)

    def test_run_button_shows_failed_status(self):
        """A run whose terminal status is 'failed' renders red.

        The colour comes from the status key, the wording from the
        endpoint's label -- the browser never decides either.
        """
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        def mock_run_export(route):
            route.fulfill(
                status=200,
                content_type='application/json',
                body=json.dumps({
                    'run_id': 1,
                    'poll_url': '/exports/runs/1/status/',
                }),
            )

        hits = []

        def mock_run_status(route):
            hits.append(route.request.url)
            route.fulfill(
                status=200,
                content_type='application/json',
                body=json.dumps({
                    'status': 'failed',
                    'label': 'Failed',
                    'complete': True,
                }),
            )

        page.route(f'**/exports/api/run/{export.id}/**', mock_run_export)
        page.route('**/runs/**/status/', mock_run_status)

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
        assert hits, 'the status endpoint was never polled'

        expect(run_button).not_to_be_disabled(timeout=3000)

    def test_run_button_shows_queued_then_started(self):
        """The UI can finally tell the two apart; both read "Running..."
        under the old endpoint."""
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        payloads = [
            {'status': 'queued', 'label': 'Queued', 'complete': False},
            {'status': 'started', 'label': 'Started', 'complete': False},
            {'status': 'completed', 'label': 'Completed', 'complete': True},
        ]

        def mock_run_export(route):
            route.fulfill(
                status=200,
                content_type='application/json',
                body=json.dumps(
                    {'run_id': 1, 'poll_url': '/exports/runs/1/status/'}
                ),
            )

        def mock_run_status(route):
            payload = payloads[0] if len(payloads) == 1 else payloads.pop(0)
            route.fulfill(
                status=200,
                content_type='application/json',
                body=json.dumps(payload),
            )

        page.route(f'**/exports/api/run/{export.id}/**', mock_run_export)
        page.route('**/runs/**/status/', mock_run_status)

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

        Asserting on #progress-bar-message would pass against a node
        Alpine is about to unmount -- that is the bug this guards.
        """
        page = _page()
        live_server = _live_server()
        data = test_data()
        export = create_export_config(data)

        def mock_run_export(route):
            route.fulfill(
                status=409,
                content_type='application/json',
                body=json.dumps({'error': 'already_running'}),
            )

        page.route(f'**/exports/api/run/{export.id}/**', mock_run_export)

        login(page, live_server, data['user'])
        navigate_to_export_details(page, live_server, export.id)

        run_button = page.locator('#run-now-button')
        run_button.click()

        expect(run_button).not_to_be_disabled(timeout=3000)
        expect(page.locator('#run-notice')).to_be_visible()
        expect(page.locator('#run-notice')).to_have_text('Already running')
