import re

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

from apps.db.models import Database

from ..models import ForwardingConfig, ForwardingDestination, ForwardingRun

User = get_user_model()


@fixture
@use('db')
def user():
    yield User.objects.create_user(
        username='fwdviewuser', email='fwd@example.com', password='pass'
    )


@fixture
def authed_client():
    client = Client()
    client.force_login(user())
    yield client


@fixture
@use('db')
def database():
    yield Database.objects.create(
        name='Test PostgreSQL',
        connection_string='postgresql://localhost/test',
    )


@fixture
def destination():
    yield ForwardingDestination.objects.create(
        name='Test API',
        api_url='https://example.com/api',
    )


@fixture
def forwarding_config():
    yield ForwardingConfig.objects.create(
        name='Test Forwarder',
        database=database(),
        destination=destination(),
        query='SELECT 1',
    )


class TestForwardersListView:
    @use(authed_client)
    def test_requires_login(self):
        client = authed_client()
        client.logout()
        response = client.get(reverse('forwarding:forwarders'))
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    @use(authed_client)
    def test_stats_in_context(self):
        response = authed_client().get(reverse('forwarding:forwarders'))
        assert response.status_code == 200
        assert 'export_stats' in response.context
        assert 'refresh_stats' in response.context
        assert 'forwarding_stats' in response.context


class TestForwardingConfigTableView:
    @use(authed_client)
    def test_requires_login(self):
        client = authed_client()
        client.logout()
        response = client.get(reverse('forwarding:config_table'))
        assert response.status_code == 302

    @use(authed_client)
    def test_returns_200(self):
        response = authed_client().get(reverse('forwarding:config_table'))
        assert response.status_code == 200

    @use(authed_client, forwarding_config)
    def test_config_appears(self):
        config = forwarding_config()
        response = authed_client().get(reverse('forwarding:config_table'))
        assert config.name in response.content.decode()

    @use(authed_client, database, destination)
    def test_pagination_default_10(self):
        db_ = database()
        dest = destination()
        for i in range(15):
            ForwardingConfig.objects.create(
                name=f'Forward {i}',
                database=db_,
                destination=dest,
                query='SELECT 1',
            )
        response = authed_client().get(reverse('forwarding:config_table'))
        shown = response.content.decode().count('Forward ')
        assert shown == 10

    @use(authed_client, forwarding_config)
    def test_etag_match_returns_no_swap(self):
        forwarding_config()
        client = authed_client()
        response = client.get(reverse('forwarding:config_table'))
        match = re.search(r'data-etag="([a-f0-9]+)"', response.content.decode())
        assert match
        etag = match.group(1)
        response2 = client.get(reverse('forwarding:config_table'), {'etag': etag})
        assert response2.get('HX-Reswap') == 'none'

    @use(authed_client, forwarding_config)
    def test_etag_mismatch_returns_content(self):
        config = forwarding_config()
        response = authed_client().get(
            reverse('forwarding:config_table'), {'etag': 'stale'}
        )
        assert response.get('HX-Reswap') is None
        assert config.name in response.content.decode()


class TestForwardingRunLogView:
    @use(authed_client, forwarding_config)
    def test_requires_login(self):
        run = ForwardingRun.objects.create(
            forwarding_config=forwarding_config(),
            status=ForwardingRun.Status.COMPLETED,
            log='hello log',
        )
        client = authed_client()
        client.logout()
        response = client.get(reverse('forwarding:run_log', args=[run.id]))
        assert response.status_code == 302

    @use(authed_client, forwarding_config)
    def test_returns_log(self):
        run = ForwardingRun.objects.create(
            forwarding_config=forwarding_config(),
            status=ForwardingRun.Status.COMPLETED,
            log='forwarding log content',
        )
        response = authed_client().get(
            reverse('forwarding:run_log', args=[run.id])
        )
        assert response.status_code == 200
        assert 'forwarding log content' in response.content.decode()

    @use(authed_client)
    def test_404_for_missing(self):
        response = authed_client().get(
            reverse('forwarding:run_log', args=[9999])
        )
        assert response.status_code == 404


class TestForwardersListPageSmoke:
    """Smoke tests: full-page renders with configs in various run states."""

    @use(authed_client)
    def test_renders_200(self):
        response = authed_client().get(reverse('forwarding:forwarders'))
        assert response.status_code == 200

    @use(authed_client)
    def test_includes_config_table_div(self):
        response = authed_client().get(reverse('forwarding:forwarders'))
        assert 'id="forwarding-config-table"' in response.content.decode()

    @use(authed_client, forwarding_config)
    def test_config_appears(self):
        config = forwarding_config()
        response = authed_client().get(reverse('forwarding:forwarders'))
        assert response.status_code == 200
        assert config.name in response.content.decode()

    @use(authed_client, forwarding_config)
    def test_renders_with_no_runs(self):
        config = forwarding_config()
        response = authed_client().get(reverse('forwarding:forwarders'))
        assert response.status_code == 200
        assert config.name in response.content.decode()

    @use(authed_client, forwarding_config)
    def test_renders_with_completed_run(self):
        ForwardingRun.objects.create(
            forwarding_config=forwarding_config(),
            status=ForwardingRun.Status.COMPLETED,
            log='Forwarded 50 rows.',
        )
        response = authed_client().get(reverse('forwarding:forwarders'))
        assert response.status_code == 200
        assert 'completed' in response.content.decode()

    @use(authed_client, forwarding_config)
    def test_renders_with_failed_run(self):
        ForwardingRun.objects.create(
            forwarding_config=forwarding_config(),
            status=ForwardingRun.Status.FAILED,
            log='Error: API returned 500.',
        )
        response = authed_client().get(reverse('forwarding:forwarders'))
        assert response.status_code == 200
        assert 'failed' in response.content.decode()

    @use(authed_client, forwarding_config)
    def test_renders_with_started_run(self):
        ForwardingRun.objects.create(
            forwarding_config=forwarding_config(),
            status=ForwardingRun.Status.STARTED,
        )
        response = authed_client().get(reverse('forwarding:forwarders'))
        assert response.status_code == 200
        assert 'started' in response.content.decode()
