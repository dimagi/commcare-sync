"""System checks for the users app."""

from django.conf import settings
from django.core.checks import Error, register

from commcare_sync.consts import SetupAccess


@register()
def check_setup_page_access(app_configs, **kwargs):
    """A typo in the data directory's settings.py would otherwise be a 500."""
    value = settings.SETUP_PAGE_ACCESS
    try:
        SetupAccess(value)
    except ValueError:
        return [
            Error(
                f'SETUP_PAGE_ACCESS is {value!r}; expected one of '
                f'{[access.value for access in SetupAccess]}.',
                id='users.E001',
            )
        ]
    return []
