import pytest
from django.core.paginator import Paginator
from django.test import RequestFactory

from commcare_sync.views import (
    compute_configs_etag,
    get_config_page_size,
    get_page_from_request,
    get_run_statuses_from_request,
    paginate,
    render_config_table,
)
from commcare_sync.consts import VALID_CONFIG_PAGE_SIZES


class _FakeConfig:
    """Stand-in for a config object: has an id but no prefetched ``_all_runs``."""

    def __init__(self, id):
        self.id = id


class TestGetConfigPageSize:
    def _get_request(self, params=''):
        factory = RequestFactory()
        return factory.get(f'/?{params}')

    @pytest.mark.parametrize('size', VALID_CONFIG_PAGE_SIZES)
    def test_valid_sizes_accepted(self, size):
        request = self._get_request(f'page_size={size}')
        assert get_config_page_size(request) == size

    def test_default_is_first_valid_size(self):
        request = self._get_request()
        assert get_config_page_size(request) == VALID_CONFIG_PAGE_SIZES[0]

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


class TestPaginate:
    def test_returns_requested_page(self):
        page = paginate(list(range(25)), 10, 2)
        assert page.number == 2
        assert list(page.object_list) == list(range(10, 20))

    def test_out_of_range_clamps_to_last_page(self):
        page = paginate(list(range(25)), 10, 999)
        assert page.number == 3
        assert list(page.object_list) == [20, 21, 22, 23, 24]

    def test_empty_object_list_returns_page_1(self):
        page = paginate([], 10, 1)
        assert page.number == 1
        assert list(page.object_list) == []


class TestRenderConfigTable:
    def _page(self):
        return Paginator([_FakeConfig(1)], 10).page(1)

    def test_matching_etag_returns_empty_no_swap_response(self):
        page = self._page()
        etag = compute_configs_etag(page.object_list)
        request = RequestFactory().get('/', {'etag': etag})
        response = render_config_table(request, page, 10, 'tmpl.html', '/url')
        assert response['HX-Reswap'] == 'none'
        assert response.content == b''
