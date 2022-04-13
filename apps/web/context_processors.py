from copy import copy
from typing import Any, Dict
from django.conf import settings
from django.http import HttpRequest
from .meta import absolute_url


def project_meta(request: HttpRequest) -> Dict[str, Any]:
    # modify these values as needed and add whatever else you want globally available here
    project_data = copy(settings.PROJECT_METADATA)
    project_data['TITLE'] = '{} | {}'.format(project_data['NAME'], project_data['DESCRIPTION'])
    return {
        'project_meta': project_data,
        'page_url': absolute_url(request.path),
        'page_title': '',
        'page_description': '',
        'page_image': '',
    }


def google_analytics_id(request: HttpRequest) -> Dict[str, Any]:
    """
    Adds google analytics id to all requests
    """
    if settings.GOOGLE_ANALYTICS_ID:
        return {
            'GOOGLE_ANALYTICS_ID': settings.GOOGLE_ANALYTICS_ID,
        }
    else:
        return {}
