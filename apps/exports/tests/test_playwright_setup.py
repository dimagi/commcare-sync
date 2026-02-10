"""
Simple smoke test to verify Playwright setup is working.
"""
import pytest
from django.urls import reverse
from playwright.sync_api import expect
from unmagic import get_request


@pytest.mark.django_db(transaction=True)
def test_playwright_can_load_page():
    """
    Smoke test: Verify Playwright can load a page.

    This is the simplest possible test to verify:
    - Playwright is installed correctly
    - Browser automation is working
    - Django live_server fixture works
    - Basic page navigation works

    Note: Uses transaction=True for live_server compatibility.
    """
    live_server = get_request().getfixturevalue('live_server')
    page = get_request().getfixturevalue('page')

    # Navigate to exports home
    page.goto(f'{live_server.url}{reverse("exports:home")}')

    # Verify page loaded (either shows exports or redirects to login)
    expect(page.locator('body')).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_page_console_logging_works():
    """
    Verify that console logging works (useful for debugging).

    Tests that the conftest.py console handler captures browser logs.
    """
    live_server = get_request().getfixturevalue('live_server')
    page = get_request().getfixturevalue('page')

    # Our conftest.py should log console messages
    page.goto(f'{live_server.url}{reverse("exports:home")}')

    # Execute some JS that logs to console
    page.evaluate('console.log("Test message from browser")')

    # If you run with -s flag, you should see the console message
    # pytest apps/exports/tests/test_playwright_setup.py::test_page_console_logging_works -s
