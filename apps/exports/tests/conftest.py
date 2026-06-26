import os

import pytest
from django.conf import settings


def pytest_configure(config):
    """
    Set environment variables for Django + Playwright compatibility.

    DJANGO_ALLOW_ASYNC_UNSAFE allows Django database operations
    to run in the async context created by Playwright tests.
    """
    os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'

    # Configure ALLOWED_HOSTS to accept localhost with any port
    # This is needed for pytest-django's live_server fixture which uses dynamic ports
    settings.ALLOWED_HOSTS = [
        'localhost',
        '127.0.0.1',
        'testserver',
        '.localhost',
    ]

    # Disable allauth rate limiting for tests
    settings.ACCOUNT_RATE_LIMITS = {
        'login_failed': None,
        'login': None,
        'signup': None,
    }


@pytest.fixture(scope='session')
def browser_context_args(browser_context_args):
    """
    Configure browser context for all Playwright tests.
    """
    return {
        **browser_context_args,
        'viewport': {
            'width': 1280,
            'height': 720,
        },
        'locale': 'en-US',
        'timezone_id': 'America/New_York',
    }
