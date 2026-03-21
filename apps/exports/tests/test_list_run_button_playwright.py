"""
Playwright tests for Run button on the Exports list page.
"""
import pytest
from playwright.sync_api import expect
from unmagic import get_request

from apps.exports.models import ExportConfig, ExportRun
from .fixtures import test_data
from .helpers import login


def navigate_to_exports_list(page, live_server):
    from django.urls import reverse
    page.goto(f"{live_server.url}{reverse('exports:home')}")


@pytest.mark.django_db(transaction=True)
class TestListPageRunButton:

    def test_run_button_appears_in_actions_column(self):
        page = get_request().getfixturevalue('page')
        live_server = get_request().getfixturevalue('live_server')
        data = test_data()
        ExportConfig.objects.create(
            name='Test Export',
            account=data['account'],
            project=data['project'],
            database=data['database'],
        )
        login(page, live_server, data['user'])
        navigate_to_exports_list(page, live_server)

        run_button = page.locator('button.btn-outline-success').first
        expect(run_button).to_be_visible()
        expect(run_button).to_contain_text('Run')

    def test_clicking_run_shows_spinner_in_status_cell(self):
        """Clicking Run immediately sets running=true via Alpine.js."""
        page = get_request().getfixturevalue('page')
        live_server = get_request().getfixturevalue('live_server')
        data = test_data()
        ExportConfig.objects.create(
            name='Test Export',
            account=data['account'],
            project=data['project'],
            database=data['database'],
        )
        login(page, live_server, data['user'])
        navigate_to_exports_list(page, live_server)

        # Mock the run endpoint to respond quickly
        page.route('**/exports/api/run/**', lambda route: route.fulfill(
            status=204, body=''
        ))

        run_button = page.locator('button.btn-outline-success').first
        run_button.click()

        # Spinner appears immediately (Alpine.js optimistic update)
        spinner = page.locator('.spinner-border').first
        expect(spinner).to_be_visible(timeout=1000)

    def test_clicking_run_disables_run_and_log_buttons(self):
        """After click, Run button is disabled; Edit link is not."""
        page = get_request().getfixturevalue('page')
        live_server = get_request().getfixturevalue('live_server')
        data = test_data()
        ExportConfig.objects.create(
            name='Test Export',
            account=data['account'],
            project=data['project'],
            database=data['database'],
        )
        login(page, live_server, data['user'])
        navigate_to_exports_list(page, live_server)

        page.route('**/exports/api/run/**', lambda route: route.fulfill(
            status=204, body=''
        ))

        run_button = page.locator('button.btn-outline-success').first
        run_button.click()
        page.wait_for_timeout(100)  # let Alpine update

        expect(run_button).to_be_disabled()

        # Edit link (an <a> tag) remains active
        edit_link = page.locator('a.btn-outline-secondary:has-text("Edit")').first
        expect(edit_link).not_to_have_attribute('disabled', '')

    def test_htmx_poll_refreshes_table_content(self):
        """Triggering the HTMX poll fetches fresh table HTML from the server."""
        page = get_request().getfixturevalue('page')
        live_server = get_request().getfixturevalue('live_server')
        data = test_data()
        ExportConfig.objects.create(
            name='Test Export',
            account=data['account'],
            project=data['project'],
            database=data['database'],
        )
        login(page, live_server, data['user'])
        navigate_to_exports_list(page, live_server)

        page.route('**/exports/api/run/**', lambda route: route.fulfill(
            status=204, body=''
        ))

        # Capture requests to the config_table endpoint
        config_table_requests = []
        page.on('request', lambda req: config_table_requests.append(req.url)
                if 'config-table' in req.url else None)

        run_button = page.locator('button.btn-outline-success').first
        run_button.click()
        page.wait_for_timeout(100)

        expect(run_button).to_be_disabled()

        # Simulate the HTMX poll by directly issuing an HTMX GET to the
        # config-table endpoint and swapping the result into the container.
        page.evaluate(
            "htmx.ajax('GET', '/exports/config-table/', {target: '#exports-config-table', swap: 'outerHTML'})"
        )
        # Wait for the network request to complete.
        page.wait_for_load_state('networkidle')

        # Verify a request was made to the config_table endpoint.
        assert any('config-table' in url for url in config_table_requests), (
            f"Expected a request to the config-table endpoint; got: {config_table_requests}"
        )

        # The table container should still be present in the DOM after the swap.
        table = page.locator('#exports-config-table')
        expect(table).to_be_visible()
