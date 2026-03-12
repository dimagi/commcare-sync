import pytest
from django.test import RequestFactory

from commcare_sync.views import (
    _VALID_CONFIG_PAGE_SIZES,
    get_config_page_size,
    get_page_from_request,
    get_run_statuses_from_request,
)

VALID_PAGE_SIZES = list(_VALID_CONFIG_PAGE_SIZES)


class TestGetConfigPageSize:
    def _req(self, params=''):
        rf = RequestFactory()
        return rf.get(f'/?{params}')

    def test_default_is_10(self):
        assert get_config_page_size(self._req()) == 10

    def test_valid_sizes_accepted(self):
        for size in VALID_PAGE_SIZES:
            assert get_config_page_size(self._req(f'page_size={size}')) == size

    def test_invalid_size_falls_back_to_default(self):
        assert get_config_page_size(self._req('page_size=7')) == 10

    def test_non_integer_falls_back_to_default(self):
        assert get_config_page_size(self._req('page_size=abc')) == 10


class TestGetPageFromRequest:
    def _req(self, params=''):
        rf = RequestFactory()
        return rf.get(f'/?{params}')

    def test_default_is_1(self):
        assert get_page_from_request(self._req()) == 1

    def test_valid_page_returned(self):
        assert get_page_from_request(self._req('page=3')) == 3

    def test_zero_clamped_to_1(self):
        assert get_page_from_request(self._req('page=0')) == 1

    def test_negative_clamped_to_1(self):
        assert get_page_from_request(self._req('page=-5')) == 1

    def test_non_integer_returns_1(self):
        assert get_page_from_request(self._req('page=abc')) == 1


class TestGetRunStatusesFromRequest:
    def test_returns_none_when_no_param(self, rf):
        request = rf.get('/')
        assert get_run_statuses_from_request(request) is None

    def test_returns_empty_list_when_sentinel_but_no_statuses(self, rf):
        request = rf.get('/', {'has_status_filter': '1'})
        assert get_run_statuses_from_request(request) == []

    def test_returns_checked_statuses(self, rf):
        request = rf.get(
            '/',
            QUERY_STRING='has_status_filter=1&status_filter=queued&status_filter=completed',
        )
        assert set(get_run_statuses_from_request(request)) == {'queued', 'completed'}

    def test_ignores_invalid_status_values(self, rf):
        request = rf.get(
            '/',
            QUERY_STRING='has_status_filter=1&status_filter=bogus&status_filter=completed',
        )
        assert set(get_run_statuses_from_request(request)) == {'completed'}
