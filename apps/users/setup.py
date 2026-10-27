"""
Creating the first admin account on a fresh install, and who may do it.
"""

import ipaddress
import logging
import secrets
from urllib.parse import urlencode, urljoin

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.http.request import split_domain_port
from django.urls import reverse

from apps.users.models import CustomUser
from commcare_sync.consts import LOCAL_HOSTNAMES, SetupAccess

ADMIN_EMAIL_VAR = 'COMMCARE_SYNC_ADMIN_EMAIL'
ADMIN_PASSWORD_VAR = 'COMMCARE_SYNC_ADMIN_PASSWORD'
TOKEN_PARAM = 'token'

# Any of these means a forwarder sits between the browser and us.
FORWARDING_HEADERS = (
    'HTTP_FORWARDED',
    'HTTP_X_FORWARDED_FOR',
    'HTTP_X_FORWARDED_HOST',
    'HTTP_X_FORWARDED_PROTO',
    'HTTP_X_REAL_IP',
)

logger = logging.getLogger(__name__)


def setup_access() -> SetupAccess:
    return SetupAccess(settings.SETUP_PAGE_ACCESS)


def may_set_up(request: HttpRequest) -> bool:
    access = setup_access()
    if access == SetupAccess.ANYONE:
        return True
    if access == SetupAccess.LOOPBACK:
        return _is_local(request)
    if access == SetupAccess.TOKEN:
        return _is_local(request) and _presents_token(request)
    return False  # NOBODY


def first_run_setup_url(base_url: str, token: str) -> str:
    """The link the launcher logs, and opens in desktop mode."""
    query = urlencode({TOKEN_PARAM: token})
    return urljoin(base_url, f'{reverse("setup")}?{query}')


def _is_local(request: HttpRequest) -> bool:
    """
    A browser on this machine, reached directly. ``REMOTE_ADDR`` alone is
    not enough: a forwarder on the same machine makes every visitor
    arrive from loopback, and a page that rebinds its host name to
    127.0.0.1 can reach us from any browser.
    """
    if not _is_loopback(request.META.get('REMOTE_ADDR', '')):
        return False
    if any(header in request.META for header in FORWARDING_HEADERS):
        return False
    host, _port = split_domain_port(request.get_host())
    return host in LOCAL_HOSTNAMES


def _presents_token(request: HttpRequest) -> bool:
    """
    The token stays in the query string, so the form posts back to the
    same URL and the POST is checked the same way. Without a configured
    token, as under ``manage.py`` against a data directory with no
    launcher running, nobody can present one.
    """
    expected = settings.SETUP_TOKEN
    if not expected:
        return False
    presented = request.GET.get(TOKEN_PARAM, '')
    # As bytes: the str form raises on a non-ASCII token instead of
    # refusing it.
    return secrets.compare_digest(presented.encode(), expected.encode())


def _is_loopback(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_loopback
    except ValueError:
        return False


def needs_setup() -> bool:
    return not CustomUser.objects.exists()


def create_first_admin(email: str, password: str) -> CustomUser | None:
    """
    Returns None when another submission got there first. SQLite begins
    the transaction IMMEDIATE, so the check and the insert run under the
    write lock; a duplicate email is refused by the database in any case.
    """
    try:
        with transaction.atomic():
            if not needs_setup():
                return None
            return CustomUser.objects.create_superuser(
                email=email, password=password
            )
    except IntegrityError:
        return None


def provision_admin(email: str | None, password: str | None) -> bool:
    """
    The non-interactive alternative to the setup page, from the
    ``COMMCARE_SYNC_ADMIN_*`` environment variables: the same validation
    as the setup form, and a no-op once any user exists.
    """
    if not (email or password):
        return False
    if not (email and password):
        logger.warning(
            '%s and %s must both be set to create an admin user; skipping',
            ADMIN_EMAIL_VAR,
            ADMIN_PASSWORD_VAR,
        )
        return False
    try:
        validate_email(email)
        validate_password(password, CustomUser(email=email))
    except ValidationError as err:
        logger.warning(
            'Not creating an admin user from %s and %s: %s',
            ADMIN_EMAIL_VAR,
            ADMIN_PASSWORD_VAR,
            ' '.join(err.messages),
        )
        return False
    return create_first_admin(email, password) is not None
