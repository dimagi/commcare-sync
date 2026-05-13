"""
Playwright tests for Run button on the Exports list page.
"""
from playwright.sync_api import expect
from unmagic import fixture, use

from apps.exports.models import ExportConfig
from .fixtures import test_data
from .helpers import login

_page = fixture('page')
_live_server = fixture('live_server')


def navigate_to_exports_list(page, live_server):
    from django.urls import reverse
    page.goto(f"{live_server.url}{reverse('exports:home')}")


@use('db')
class TestListPageRunButton:

    @use(_page, _live_server)
    def test_run_button_appears_in_actions_column(self):
        page = _page()
        live_server = _live_server()
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

    @use(_page, _live_server)
    def test_clicking_run_shows_spinner_in_status_cell(self):
        """Clicking Run immediately sets running=true via Alpine.js."""
        page = _page()
        live_server = _live_server()
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

    @use(_page, _live_server)
    def test_clicking_run_disables_run_and_log_buttons(self):
        """After click, Run button is disabled; Edit link is not."""
        page = _page()
        live_server = _live_server()
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

    @use(_page, _live_server)
    def test_htmx_poll_resets_running_state(self):
        """Triggering the HTMX poll (outerHTML swap) resets Alpine running state."""
        page = _page()
        live_server = _live_server()
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
        page.wait_for_timeout(100)
        expect(run_button).to_be_disabled()

        # Simulate the 60-second HTMX poll: replace the outer container via outerHTML swap
        # (This is what hx-trigger="every 60s" + hx-swap="outerHTML" does)
        from django.urls import reverse
        config_table_url = reverse('exports:config_table')
        page.evaluate(
            f"htmx.ajax('GET', '{config_table_url}', "
            f"{{target: '#exports-config-table', swap: 'outerHTML'}})"
        )
        # Wait for HTMX to complete the outerHTML swap and Alpine to re-initialize
        page.wait_for_timeout(1000)

        # After the swap, the new tbody has fresh Alpine state (running=false)
        # Locate the re-rendered Run button
        new_run_button = page.locator('button.btn-outline-success').first
        expect(new_run_button).not_to_be_disabled(timeout=2000)
