import pytest

from commcare_sync.consts import LOOPBACK_IPV4
from commcare_sync.launcher.env import Mode
from commcare_sync.launcher.listen import (
    DEFAULT_PORT,
    DEFAULT_SERVER_BIND,
    PortUnavailableError,
    open_listening_socket,
    resolve_listen_address,
    server_url,
)
from commcare_sync.tests.helpers import listening_socket

DESKTOP = Mode.DESKTOP
SERVER = Mode.SERVER


class TestListenAddress:
    @pytest.mark.parametrize(
        'mode, expected',
        [
            (SERVER, (DEFAULT_SERVER_BIND, DEFAULT_PORT)),
            (DESKTOP, (LOOPBACK_IPV4, 0)),
        ],
    )
    def test_defaults(self, mode, expected):
        assert resolve_listen_address(mode, bind=None, port=None) == expected

    def test_explicit_values_are_honored(self):
        address = resolve_listen_address(SERVER, bind='10.0.0.1', port=9000)
        assert address == ('10.0.0.1', 9000)

    def test_port_zero_picks_a_free_port(self):
        with open_listening_socket(LOOPBACK_IPV4, 0) as sock:
            assert sock.getsockname()[1] > 0

    def test_port_in_use_is_rejected(self):
        with listening_socket() as taken:
            port = taken.getsockname()[1]
            with pytest.raises(PortUnavailableError) as exc_info:
                open_listening_socket(LOOPBACK_IPV4, port)
        assert f'{LOOPBACK_IPV4}:{port}' in str(exc_info.value)
        assert 'already in use' in str(exc_info.value)

    def test_other_bind_failures_say_what_went_wrong(self):
        with pytest.raises(PortUnavailableError) as exc_info:
            open_listening_socket('203.0.113.1', 0)  # TEST-NET, not local
        assert 'already in use' not in str(exc_info.value)
        assert 'Cannot listen on 203.0.113.1:0' in str(exc_info.value)

    def test_wildcard_bind_is_reported_as_loopback(self):
        assert server_url('0.0.0.0', 8000) == 'http://127.0.0.1:8000/'

    def test_specific_bind_is_reported_as_itself(self):
        assert server_url('10.0.0.1', 8000) == 'http://10.0.0.1:8000/'

    def test_an_ipv6_bind_is_bracketed(self):
        assert server_url('::1', 8000) == 'http://[::1]:8000/'

    def test_the_ipv6_wildcard_is_reported_as_loopback(self):
        assert server_url('::', 8000) == 'http://127.0.0.1:8000/'

    def test_an_ipv6_bind_failure_is_bracketed(self):
        with listening_socket('::1') as taken:
            port = taken.getsockname()[1]
            with pytest.raises(PortUnavailableError) as exc_info:
                open_listening_socket('::1', port)
        assert f'[::1]:{port}' in str(exc_info.value)
