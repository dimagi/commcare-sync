import doctest

import pytest

from apps.web.templatetags import meta_tags


def test_doctests():
    results = doctest.testmod(meta_tags, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0


@pytest.fixture
def project_meta():
    return {
        'NAME': 'Test App',
        'TITLE': 'Test App - Welcome',
        'DESCRIPTION': 'A test application',
        'IMAGE': 'https://example.com/default-image.png',
    }


@pytest.mark.parametrize(
    ('page_title', 'expected'),
    [
        ('About Us', 'About Us | Test App'),
        (None, 'Test App - Welcome'),
        ('', 'Test App - Welcome'),
    ],
)
def test_get_title(project_meta, page_title, expected):
    result = meta_tags.get_title(project_meta, page_title)
    assert result == expected


@pytest.mark.parametrize(
    ('page_description', 'expected'),
    [
        ('Custom page description', 'Custom page description'),
        (None, 'A test application'),
        ('', 'A test application'),
    ],
)
def test_get_description(project_meta, page_description, expected):
    result = meta_tags.get_description(project_meta, page_description)
    assert result == expected


@pytest.mark.parametrize(
    ('page_image', 'expected'),
    [
        (
            'https://example.com/custom-image.png',
            'https://example.com/custom-image.png',
        ),
        (None, 'https://example.com/default-image.png'),
        ('', 'https://example.com/default-image.png'),
    ],
)
def test_get_image_url(project_meta, page_image, expected):
    result = meta_tags.get_image_url(project_meta, page_image)
    assert result == expected


def test_get_image_url_with_relative_path(project_meta, db):
    from django.contrib.sites.models import Site

    Site.objects.get_or_create(
        pk=1,
        defaults={'domain': 'example.com', 'name': 'Example'},
    )

    result = meta_tags.get_image_url(project_meta, '/static/custom.png')
    assert result.startswith('http')
    assert 'custom.png' in result
