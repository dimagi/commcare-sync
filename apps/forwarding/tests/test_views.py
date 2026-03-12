import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.exports.models import ExportDatabase

from ..models import ForwardingConfig, ForwardingDestination, ForwardingRun

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='fwdviewuser', email='fwd@example.com', password='pass'
    )


@pytest.fixture
def client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def database(db, user):
    return ExportDatabase.objects.create(
        name='Test PostgreSQL',
        connection_string='postgresql://localhost/test',
        owner=user,
    )


@pytest.fixture
def destination(db, user):
    return ForwardingDestination.objects.create(
        name='Test API',
        api_url='https://example.com/api',
        owner=user,
    )


@pytest.fixture
def forwarding_config(db, user, database, destination):
    return ForwardingConfig.objects.create(
        name='Test Forwarder',
        database=database,
        destination=destination,
        query='SELECT 1',
        created_by=user,
    )


class TestForwardersListView:
    def test_requires_login(self, client, user):
        client.logout()
        url = reverse('forwarding:forwarders')
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_stats_in_context(self, client, db):
        url = reverse('forwarding:forwarders')
        response = client.get(url)
        assert response.status_code == 200
        assert 'export_stats' in response.context
        assert 'refresh_stats' in response.context
        assert 'forwarding_stats' in response.context


class TestForwardingConfigTableView:
    def test_requires_login(self, client, user):
        client.logout()
        response = client.get(reverse('forwarding:config_table'))
        assert response.status_code == 302

    def test_returns_200(self, client, db):
        response = client.get(reverse('forwarding:config_table'))
        assert response.status_code == 200

    def test_config_appears(self, client, forwarding_config):
        response = client.get(reverse('forwarding:config_table'))
        assert forwarding_config.name in response.content.decode()

    def test_pagination_default_10(self, client, user, database, destination):
        for i in range(15):
            ForwardingConfig.objects.create(
                name=f'Forward {i}',
                database=database,
                destination=destination,
                query='SELECT 1',
                created_by=user,
            )
        response = client.get(reverse('forwarding:config_table'))
        shown = response.content.decode().count('Forward ')
        assert shown == 10

    def test_etag_match_returns_no_swap(self, client, forwarding_config):
        response = client.get(reverse('forwarding:config_table'))
        match = re.search(r'data-etag="([a-f0-9]+)"', response.content.decode())
        assert match
        etag = match.group(1)
        response2 = client.get(reverse('forwarding:config_table'), {'etag': etag})
        assert response2.get('HX-Reswap') == 'none'

    def test_etag_mismatch_returns_content(self, client, forwarding_config):
        response = client.get(reverse('forwarding:config_table'), {'etag': 'stale'})
        assert response.get('HX-Reswap') is None
        assert forwarding_config.name in response.content.decode()


class TestForwardingRunLogView:
    def test_requires_login(self, client, user, forwarding_config):
        run = ForwardingRun.objects.create(
            forwarding_config=forwarding_config,
            status=ForwardingRun.Status.COMPLETED,
            log='hello log',
        )
        client.logout()
        response = client.get(reverse('forwarding:run_log', args=[run.id]))
        assert response.status_code == 302

    def test_returns_log(self, client, forwarding_config):
        run = ForwardingRun.objects.create(
            forwarding_config=forwarding_config,
            status=ForwardingRun.Status.COMPLETED,
            log='forwarding log content',
        )
        response = client.get(reverse('forwarding:run_log', args=[run.id]))
        assert response.status_code == 200
        assert 'forwarding log content' in response.content.decode()

    def test_404_for_missing(self, client):
        response = client.get(reverse('forwarding:run_log', args=[9999]))
        assert response.status_code == 404
