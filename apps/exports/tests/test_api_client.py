import pytest
import requests

from apps.exports.api_client import get_filename_from_response


@pytest.mark.parametrize(
    ('content_disposition', 'expected'),
    [
        ('attachment; filename=config.xlsx', 'config.xlsx'),
        ('attachment; filename="config.xlsx"', 'config.xlsx'),
        ('attachment; filename="report 2024.xlsx"', 'report 2024.xlsx'),
        ('inline; filename=data.xlsx', 'data.xlsx'),
        ('attachment; filename*=UTF-8\'\'config.xlsx', 'config.xlsx'),
        (
            'attachment; filename*=UTF-8\'\'report%202024.xlsx',
            'report 2024.xlsx',
        ),
        (
            'attachment; filename="test.xlsx"; filename*=UTF-8\'\'test.xlsx',
            'test.xlsx',
        ),
        ('attachment', 'default.xlsx'),
        ('', 'default.xlsx'),
    ],
)
def test_get_filename_from_response_with_header(content_disposition, expected):
    response = requests.Response()
    response.headers['Content-Disposition'] = content_disposition
    filename = get_filename_from_response(response, default='default.xlsx')
    assert filename == expected


def test_get_filename_from_response_without_header():
    response = requests.Response()
    filename = get_filename_from_response(response, default='default.xlsx')
    assert filename == 'default.xlsx'


def test_get_filename_from_response_no_default():
    response = requests.Response()
    filename = get_filename_from_response(response)
    assert filename == 'filename'
