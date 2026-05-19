import doctest

import pytest

from apps.exports.models import ExportRunBase
from apps.exports.templatetags import exports_tags


def test_doctests():
    results = doctest.testmod(exports_tags, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0


@pytest.mark.parametrize(
    ('status', 'expected_icon', 'expected_class'),
    [
        (ExportRunBase.Status.COMPLETED, 'fa-circle-check', 'text-success'),
        (ExportRunBase.Status.FAILED, 'fa-circle-exclamation', 'text-danger'),
        (ExportRunBase.Status.STARTED, 'fa-play-circle', 'text-primary'),
        (ExportRunBase.Status.MULTIPLE, 'fa-exclamation-triangle', 'text-warning'),
        (ExportRunBase.Status.QUEUED, 'fa-ellipsis-h', 'text-muted'),
        (ExportRunBase.Status.SKIPPED, 'fa-ban', 'text-muted'),
    ],
)
def test_to_status_icon(status, expected_icon, expected_class):
    result = exports_tags.to_status_icon(status)

    assert '<i' in result
    assert expected_icon in result
    assert expected_class in result
    assert f'title="{status}"' in result
    assert 'fa' in result
    assert '</i>' in result


def test_to_status_icon_unknown_status():
    result = exports_tags.to_status_icon('unknown_status')

    assert '<i' in result
    assert 'title="unknown_status"' in result
    assert 'fa' in result


def test_to_status_icon_returns_safe_string():
    from django.utils.safestring import SafeString

    result = exports_tags.to_status_icon(ExportRunBase.Status.COMPLETED)
    assert isinstance(result, SafeString)
