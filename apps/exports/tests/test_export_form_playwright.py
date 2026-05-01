"""
Playwright structural tests for Export form.

Tests that verify HTML structure, Alpine.js attributes, and HTMX configuration
without requiring full integration testing or API mocking.
"""
import pytest
from django.urls import reverse
from playwright.sync_api import expect
from unmagic import fixture, use

from .fixtures import test_data
from .helpers import login, navigate_to_create_export

_page = fixture('page')
_live_server = fixture('live_server')


@pytest.mark.django_db(transaction=True)
class TestExportFormStructure:
    """Test form structure and attributes."""

    @use(_page, _live_server)
    def test_export_form_has_required_fields(self):
        """Test that export form contains all required fields."""
        page = _page()
        live_server = _live_server()
        data = test_data()

        login(page, live_server, data['user'])
        navigate_to_create_export(page, live_server)

        # Verify required form fields exist
        expect(page.locator('#id_name')).to_be_visible()
        expect(page.locator('#id_project')).to_be_visible()
        expect(page.locator('#id_account')).to_be_visible()
        expect(page.locator('#id_database')).to_be_visible()
        expect(page.locator('#id_config_file_select')).to_be_visible()

    @use(_page, _live_server)
    def test_alpine_attributes_present(self):
        """Test that Alpine.js attributes are configured."""
        page = _page()
        live_server = _live_server()
        data = test_data()

        login(page, live_server, data['user'])
        navigate_to_create_export(page, live_server)

        # Check Alpine.js attributes on config select
        config_select = page.locator('#id_config_file_select')
        expect(config_select).to_have_attribute('x-model', 'selectedConfig')
        expect(config_select).to_have_attribute(':disabled', 'loading')

    @use(_page, _live_server)
    def test_htmx_attributes_present(self):
        """Test that HTMX attributes are configured."""
        page = _page()
        live_server = _live_server()
        data = test_data()

        login(page, live_server, data['user'])
        navigate_to_create_export(page, live_server)

        # Check HTMX attributes on config select
        config_select = page.locator('#id_config_file_select')
        expect(config_select).to_have_attribute(
            'hx-get',
            reverse('exports:fetch_config_files')
        )

        # Check hx-trigger exists (value varies by form context)
        expect(config_select).to_have_attribute('hx-trigger', 'refresh')
        expect(config_select).to_have_attribute('hx-swap', 'innerHTML')
        expect(config_select).to_have_attribute('hx-target', 'this')

        # Check onchange event on project select (triggers refresh)
        project_select = page.locator('#id_project')
        expect(project_select).to_have_attribute(
            'onchange',
            "htmx.trigger('#id_config_file_select', 'refresh')"
        )


@pytest.mark.django_db
class TestHTMXEndpoints:
    """Test HTMX endpoint configuration (no browser needed)."""

    def test_fetch_config_files_endpoint_exists(self):
        """Test that fetch_config_files endpoint is properly configured."""
        url = reverse('exports:fetch_config_files')
        assert url == '/exports/api/fetch-config-files/'
