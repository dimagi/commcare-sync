VALID_CONFIG_PAGE_SIZES = (10, 20, 50)

# A browser on this machine, as it appears in URLs and ``Host`` headers,
# and as the launcher may bind it in desktop mode.
LOOPBACK_IPV4 = '127.0.0.1'
LOOPBACK_IPV6 = '::1'
LOCAL_HOSTNAMES = ('localhost', LOOPBACK_IPV4, f'[{LOOPBACK_IPV6}]')
LOCAL_BIND_ADDRESSES = ('localhost', LOOPBACK_IPV4, LOOPBACK_IPV6)
