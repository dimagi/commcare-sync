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
