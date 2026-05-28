"""
Shared helper functions for Playwright tests.
"""
from django.urls import reverse


def login(page, live_server, user):
    """Helper to log in a user."""
    page.goto(f'{live_server.url}/accounts/login/')
    page.fill('input[name="login"]', user.email)
    page.fill('input[name="password"]', 'testpass')
    page.click('button[type="submit"]')
    page.wait_for_url(lambda url: '/accounts/login/' not in url)


def navigate_to_create_export(page, live_server):
    """Helper to navigate to the create export page."""
    page.goto(f'{live_server.url}{reverse("exports:create_export_config")}')


def navigate_to_export_details(page, live_server, export_id):
    """Helper to navigate to export details page."""
    page.goto(f'{live_server.url}{reverse("exports:export_details", args=[export_id])}')
