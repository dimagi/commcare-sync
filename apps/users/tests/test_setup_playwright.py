"""Playwright test for the first-run setup page.

A fresh install has no users, so visiting any page must land on
``/setup/``; filling in the form should create the admin, log them in,
and land on the home page.
"""

from django.urls import reverse
from playwright.sync_api import expect
from unmagic import fixture, use

from apps.users.models import CustomUser

_page = fixture('page')
_live_server = fixture('live_server')

VALID_PASSWORD = 'S3curePass!23'  # noqa: S105 - test fixture password


@use('db', 'transactional_db', _live_server, _page)
def test_fresh_install_redirects_to_setup_and_creates_the_admin():
    page = _page()
    live_server = _live_server()

    page.goto(live_server.url + reverse('web:home'))
    page.wait_for_url(f'**{reverse("setup")}')

    page.fill('input[name="email"]', 'admin@example.com')
    page.fill('input[name="password1"]', VALID_PASSWORD)
    page.fill('input[name="password2"]', VALID_PASSWORD)
    page.click('button[type="submit"]')

    page.wait_for_url(lambda url: reverse('setup') not in url)
    # Logged in: home redirects an authenticated user on to exports:home.
    expect(page).to_have_url(live_server.url + reverse('exports:home'))

    user = CustomUser.objects.get(email='admin@example.com')
    assert user.is_superuser
