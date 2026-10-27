from enum import StrEnum

VALID_CONFIG_PAGE_SIZES = (10, 20, 50)

# A browser on this machine, as it appears in URLs and ``Host`` headers,
# and as the launcher may bind it in desktop mode.
LOOPBACK_IPV4 = '127.0.0.1'
LOOPBACK_IPV6 = '::1'
LOCAL_HOSTNAMES = ('localhost', LOOPBACK_IPV4, f'[{LOOPBACK_IPV6}]')
LOCAL_BIND_ADDRESSES = ('localhost', LOOPBACK_IPV4, LOOPBACK_IPV6)


class SetupAccess(StrEnum):
    """Who may use the first-run setup page while no user exists."""

    ANYONE = 'anyone'
    # A browser on the same machine.
    LOOPBACK = 'loopback'
    # A browser on the same machine, opened at the link the launcher
    # logged: another account on this machine cannot read that log.
    TOKEN = 'token'
    # Create the admin with the environment variables instead.
    NOBODY = 'nobody'
