"""
Playwright tests for Run button on the Exports list page.
"""
from django.urls import reverse
from playwright.sync_api import expect
from unmagic import fixture, use

from apps.exports.models import ExportConfig, ExportRun

from .fixtures import test_data
from .helpers import login

_page = fixture('page')
_live_server = fixture('live_server')


def navigate_to_exports_list(page, live_server):
    page.goto(f"{live_server.url}{reverse('exports:home')}")


@use('db', 'transactional_db', _page, _live_server)
class TestListPageRunButton:

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

        run_button = page.locator('button.btn-outline-primary').first
        expect(run_button).to_be_visible()
        expect(run_button).to_contain_text('Run')

    def test_clicking_run_on_a_stale_table_says_why_nothing_started(self):
        # The Run button is only enabled while the table shows no active
        # run. A run that began after the table last refreshed still
        # blocks the click, and the user is told why.
        page = _page()
        live_server = _live_server()
        data = test_data()
        config = ExportConfig.objects.create(
            name='Test Export',
            account=data['account'],
            project=data['project'],
            database=data['database'],
        )
        login(page, live_server, data['user'])
        navigate_to_exports_list(page, live_server)
        run_button = page.locator('button.btn-outline-primary').first
        expect(run_button).to_be_enabled()

        ExportRun.objects.create(
            config=config, status=ExportRun.Status.STARTED
        )
        run_button.click()

        alert = page.locator('#app-messages .alert')
        expect(alert).to_be_visible(timeout=5000)
        expect(alert).to_contain_text(
            'Not started: another run is already running.'
        )
        # The table refreshes to show the run that blocked the click.
        run_button = page.locator('button.btn-outline-primary').first
        expect(run_button).to_be_disabled(timeout=5000)
