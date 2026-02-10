"""
Playwright tests with API mocking for Export form.

Tests Alpine.js and HTMX functionality with mocked API responses.
"""
import pytest
from playwright.sync_api import Route, expect
from unmagic import get_request

from .fixtures import test_data
from .helpers import login, navigate_to_create_export


def mock_config_files_response(route: Route):
    """Mock the fetch_config_files HTMX endpoint."""
    html_response = """
        <option value="">Select a config file...</option>
        <option value="https://test.commcarehq.org/a/test-domain/export/config/123/">
            Test Config 1
        </option>
        <option value="https://test.commcarehq.org/a/test-domain/export/config/456/">
            Test Config 2
        </option>
    """
    route.fulfill(
        status=200,
        content_type='text/html',
        body=html_response
    )


def mock_config_files_error(route: Route):
    """Mock an error response from fetch_config_files."""
    html_response = """
        <option value="">Error loading configs</option>
        <ul class="errorlist" id="config-fetch-errors" hx-swap-oob="true">
            <li>Missing account_id or project_ids</li>
        </ul>
    """
    route.fulfill(
        status=200,
        content_type='text/html',
        body=html_response
    )


@pytest.mark.django_db(transaction=True)
class TestExportFormWithMockedAPI:
    """Test export form with mocked HTMX responses."""

    def test_full_form_flow_with_config_selection(self):
        """Test complete form flow from load to config selection."""
        page = get_request().getfixturevalue('page')
        live_server = get_request().getfixturevalue('live_server')
        data = test_data()

        # Setup: Mock the HTMX endpoint
        page.route(
            '**/exports/api/fetch-config-files/*',
            mock_config_files_response
        )

        login(page, live_server, data['user'])
        navigate_to_create_export(page, live_server)

        # Fill out form fields
        page.fill('#id_name', 'My Test Export')

        # Select account and project to trigger HTMX config fetch
        page.select_option('#id_account', str(data['account'].id))
        page.select_option('#id_project', str(data['project'].id))

        # Wait for HTMX to populate config options from our mock
        # (3 total: 1 placeholder + 2 configs)
        expect(page.locator('#id_config_file_select option')).to_have_count(
            3,
            timeout=10000,
        )

        # Select a config
        page.select_option(
            '#id_config_file_select',
            'https://test.commcarehq.org/a/test-domain/export/config/123/'
        )

        # Verify hidden input updated via Alpine x-model
        hidden_input = page.locator('#id_det_config_url')
        expect(hidden_input).to_have_value(
            'https://test.commcarehq.org/a/test-domain/export/config/123/'
        )

    def test_loading_spinner_during_fetch(self):
        """Test that Alpine loading state mechanism is properly configured."""
        page = get_request().getfixturevalue('page')
        live_server = get_request().getfixturevalue('live_server')
        data = test_data()

        page.route(
            '**/exports/api/fetch-config-files/*',
            mock_config_files_response,
        )

        login(page, live_server, data['user'])
        navigate_to_create_export(page, live_server)

        # Verify loading state elements are configured correctly
        config_select = page.locator('#id_config_file_select')

        # Check that Alpine.js loading handlers are present
        expect(config_select).to_have_attribute(
            '@htmx:before-request',
            'loading = true',
        )
        expect(config_select).to_have_attribute(
            '@htmx:after-request',
            'loading = false',
        )

        # Check that config select has :disabled binding
        expect(config_select).to_have_attribute(':disabled', 'loading')

        # Verify loading text exists with x-show binding
        loading_text = page.locator(
            'text=Loading available configs from CommCare HQ'
        )
        expect(loading_text).to_have_attribute('x-show', 'loading')

    def test_error_handling_when_fetch_fails(self):
        """Test that errors from config fetch are handled gracefully."""
        page = get_request().getfixturevalue('page')
        live_server = get_request().getfixturevalue('live_server')
        data = test_data()

        # Mock error response
        page.route(
            '**/exports/api/fetch-config-files/*',
            mock_config_files_error,
        )

        login(page, live_server, data['user'])
        navigate_to_create_export(page, live_server)

        # Trigger HTMX request
        page.select_option('#id_account', str(data['account'].id))
        page.select_option('#id_project', str(data['project'].id))

        # Wait for HTMX to update the select with error option
        # Check that the error message appears in the select's HTML content
        config_select = page.locator('#id_config_file_select')
        expect(config_select).to_contain_text('Error loading configs')

        # Verify error list is rendered like Django field errors
        error_list = page.locator('#config-fetch-errors')
        expect(error_list).to_have_class('errorlist')
        expect(error_list).to_contain_text('Missing account_id or project_ids')
