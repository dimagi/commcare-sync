import pytest
from django.test import RequestFactory

from commcare_sync.views import get_config_page_size, get_page_from_request

VALID_PAGE_SIZES = [10, 20, 50]


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
