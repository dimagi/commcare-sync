"""
Creating the first admin account on a fresh install.
"""

import logging

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.users.models import CustomUser

ADMIN_EMAIL_VAR = 'COMMCARE_SYNC_ADMIN_EMAIL'
ADMIN_PASSWORD_VAR = 'COMMCARE_SYNC_ADMIN_PASSWORD'

logger = logging.getLogger(__name__)


def provision_admin(email: str | None, password: str | None) -> bool:
    """
    The non-interactive alternative to a setup page, from the
    ``COMMCARE_SYNC_ADMIN_*`` environment variables: the same validation
    as the forms, and a no-op once any user exists.
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
    if CustomUser.objects.exists():
        return False
    CustomUser.objects.create_superuser(email=email, password=password)
    return True
