from django.test import RequestFactory

from commcare_sync.views import (
    get_config_page_size,
    get_page_from_request,
    get_run_statuses_from_request,
)
from commcare_sync.consts import VALID_CONFIG_PAGE_SIZES


class TestGetConfigPageSize:
    def _get_request(self, params=''):
        factory = RequestFactory()
        return factory.get(f'/?{params}')

    def test_default_is_first_valid_size(self):
        request = self._get_request()
        assert get_config_page_size(request) == VALID_CONFIG_PAGE_SIZES[0]

    def test_valid_sizes_accepted(self):
        for size in VALID_CONFIG_PAGE_SIZES:
            request = self._get_request(f'page_size={size}')
            assert get_config_page_size(request) == size

    def test_invalid_size_falls_back_to_default(self):
        request = self._get_request('page_size=7')
        default = VALID_CONFIG_PAGE_SIZES[0]
        assert get_config_page_size(request) == default

    def test_non_integer_falls_back_to_default(self):
        request = self._get_request('page_size=abc')
        default = VALID_CONFIG_PAGE_SIZES[0]
        assert get_config_page_size(request) == default


class TestGetPageFromRequest:
    def _get_request(self, params=''):
        factory = RequestFactory()
        return factory.get(f'/?{params}')

    def test_default_is_1(self):
        assert get_page_from_request(self._get_request()) == 1

    def test_valid_page_returned(self):
        assert get_page_from_request(self._get_request('page=3')) == 3

    def test_zero_clamped_to_1(self):
        assert get_page_from_request(self._get_request('page=0')) == 1

    def test_negative_clamped_to_1(self):
        assert get_page_from_request(self._get_request('page=-5')) == 1

    def test_non_integer_returns_1(self):
        assert get_page_from_request(self._get_request('page=abc')) == 1


class TestGetRunStatusesFromRequest:
    def _get_request(self, params=''):
        factory = RequestFactory()
        return factory.get(f'/?{params}')

    def test_returns_empty_list_when_no_statuses(self):
        request = self._get_request()
        assert get_run_statuses_from_request(request) == []

    def test_returns_checked_statuses(self):
        request = self._get_request('&'.join((
            'status_filter=queued',
            'status_filter=completed',
        )))
        assert set(get_run_statuses_from_request(request)) == {
            'queued',
            'completed',
        }

    def test_ignores_invalid_status_values(self):
        request = self._get_request('&'.join((
            'status_filter=bogus',
            'status_filter=completed',
        )))
        assert set(get_run_statuses_from_request(request)) == {'completed'}
