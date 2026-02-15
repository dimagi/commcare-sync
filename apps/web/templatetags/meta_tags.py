from django import template
from django.templatetags.static import static
from ..meta import absolute_url

register = template.Library()


@register.filter
def get_title(project_meta, page_title=None):
    """
    Format page title with project name.

    >>> meta = {'NAME': 'MyApp', 'TITLE': 'MyApp - Home'}
    >>> get_title(meta, 'About')
    'About | MyApp'
    >>> get_title(meta)
    'MyApp - Home'
    """
    if page_title:
        return '{} | {}'.format(page_title, project_meta['NAME'])
    else:
        return project_meta['TITLE']


@register.filter
def get_description(project_meta, page_description=None):
    """
    Get page description, falling back to project default.

    >>> meta = {'DESCRIPTION': 'Default description'}
    >>> get_description(meta, 'Custom description')
    'Custom description'
    >>> get_description(meta)
    'Default description'
    """
    return page_description or project_meta['DESCRIPTION']


@register.filter
def get_image_url(project_meta, page_image=None):
    """
    Get image URL, converting relative paths to absolute URLs.

    >>> meta = {'IMAGE': 'https://example.com/default.png'}
    >>> get_image_url(meta, 'https://example.com/custom.png')
    'https://example.com/custom.png'
    >>> get_image_url(meta)
    'https://example.com/default.png'
    """
    if page_image and page_image.startswith('/'):
        page_image = absolute_url(static(page_image))
    return page_image or project_meta['IMAGE']
