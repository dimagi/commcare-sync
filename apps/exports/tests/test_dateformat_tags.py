import doctest
from datetime import timedelta

import pytest

from apps.web.templatetags import dateformat_tags


def test_doctests():
    results = doctest.testmod(dateformat_tags, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0


@pytest.mark.parametrize(
    ('delta', 'expected'),
    [
        (timedelta(days=7), '7 days'),
        (timedelta(seconds=45), '45 seconds'),
        (timedelta(minutes=3, seconds=4), '3 minutes 4 seconds'),
        (timedelta(days=1, seconds=30), '1 days 30 seconds'),
        (timedelta(hours=25, minutes=30), '1 days 1 hours 30 minutes'),
        (
            timedelta(hours=2, minutes=3, seconds=4),
            '2 hours 3 minutes 4 seconds',
        ),
        (
            timedelta(days=1, hours=2, minutes=3, seconds=4),
            '1 days 2 hours 3 minutes 4 seconds',
        ),
        (
            timedelta(days=365, hours=23, minutes=59, seconds=59),
            '365 days 23 hours 59 minutes 59 seconds',
        ),
        (None, '---'),
    ],
)
def test_readable_timedelta(delta, expected):
    result = dateformat_tags.readable_timedelta(delta)
    assert result == expected


def test_readable_timedelta_edge_cases():
    assert dateformat_tags.readable_timedelta(timedelta(seconds=0)) == '---'
    assert dateformat_tags.readable_timedelta(timedelta()) == '---'
    assert dateformat_tags.readable_timedelta(0) == '---'
    assert dateformat_tags.readable_timedelta('') == '---'
    assert dateformat_tags.readable_timedelta(False) == '---'
