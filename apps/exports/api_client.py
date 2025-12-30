from typing import TypedDict

import requests
from django.core.files.base import ContentFile


DET_EXPORT_INSTANCE_API = "{server_url}/a/{domain}/api/det_export_instance/v1/"


class DETExportInstance(TypedDict):
    name: str
    det_config_url: str


def fetch_available_configs(
    server_url: str,
    domain: str,
    username: str,
    api_key: str,
) -> list[DETExportInstance]:
    """
    Fetch available config files from CommCare HQ.

    :param server_url: The CommCare server URL
    :param domain: The CommCare project domain
    :param username: The account username
    :param api_key: The account API key

    :returns: List of dicts that include 'name' and 'det_config_url' keys

    :raises requests.exceptions.RequestException: If the API request fails
    """
    url = DET_EXPORT_INSTANCE_API.format(
        server_url=server_url.rstrip('/'),
        domain=domain,
    )
    response = requests.get(
        url,
        headers={
            'Authorization': f'ApiKey {username}:{api_key}',
            'Accept': 'application/json',
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data.get('objects', [])


def download_config_file(url: str, username: str, api_key: str) -> ContentFile:
    """
    Download a DET config file from CommCare HQ.

    :param url: The det_config_url from the available configs list
    :param username: The account username
    :param api_key: The account API key

    :returns: ContentFile object containing the downloaded config file

    :raises requests.exceptions.RequestException: If the download fails
    """
    response = requests.get(
        url,
        headers={
            'Authorization': f'ApiKey {username}:{api_key}',
            'Accept': 'application/json',
        },
        timeout=30,
    )
    response.raise_for_status()
    filename = url.split('/')[-1] or 'config.xlsx'
    return ContentFile(response.content, name=filename)
