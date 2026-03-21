import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.db.models import Database
from apps.forwarding.models import ForwardingConfig, ForwardingDestination, ForwardingRun

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='detailsuser_fwd', email='dfwd@example.com', password='pass'
    )


@pytest.fixture
def client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def database(db):
    return Database.objects.create(
        name='TestDB',
        connection_string='postgresql://localhost/test',
    )


@pytest.fixture
def destination(db):
    return ForwardingDestination.objects.create(
        name='Test API',
        api_url='https://example.com/api',
    )


@pytest.fixture
def forwarding_config(db, user, database, destination):
    return ForwardingConfig.objects.create(
        name='Test Forwarder',
        database=database,
        destination=destination,
        query='SELECT 1',
    )


@pytest.mark.django_db
class TestForwarderDetailsSmoke:
    def test_returns_200(self, client, forwarding_config):
        response = client.get(
            reverse('forwarding:forwarder_details', args=[forwarding_config.id])
        )
        assert response.status_code == 200

    def test_no_details_suffix_in_heading(self, client, forwarding_config):
        response = client.get(
            reverse('forwarding:forwarder_details', args=[forwarding_config.id])
        )
        assert '- Details' not in response.content.decode()

    def test_run_table_present(self, client, forwarding_config):
        response = client.get(
            reverse('forwarding:forwarder_details', args=[forwarding_config.id])
        )
        assert 'id="run-table"' in response.content.decode()

    def test_status_filter_dropdown_present(self, client, forwarding_config):
        response = client.get(
            reverse('forwarding:forwarder_details', args=[forwarding_config.id])
        )
        content = response.content.decode()
        assert 'status-filter-form' in content
        assert 'has_status_filter' in content

    def test_run_history_section_present(self, client, forwarding_config):
        response = client.get(
            reverse('forwarding:forwarder_details', args=[forwarding_config.id])
        )
        content = response.content.decode()
        assert 'Run History' in content
        assert 'id="run-table"' in content

    def test_schedule_column_present(self, client, forwarding_config):
        response = client.get(
            reverse('forwarding:forwarder_details', args=[forwarding_config.id])
        )
        assert 'Schedule' in response.content.decode()


@pytest.mark.django_db
class TestForwardingRunHistoryTableEndpoint:
    def test_returns_200(self, client, forwarding_config):
        assert (
            client.get(
                reverse('forwarding:run_history_table', args=[forwarding_config.id])
            ).status_code
            == 200
        )

    def test_status_filter_excludes_unchecked(self, client, forwarding_config):
        completed_run = ForwardingRun.objects.create(
            forwarding_config=forwarding_config,
            status=ForwardingRun.Status.COMPLETED,
        )
        failed_run = ForwardingRun.objects.create(
            forwarding_config=forwarding_config,
            status=ForwardingRun.Status.FAILED,
        )
        url = reverse('forwarding:run_history_table', args=[forwarding_config.id])
        content = client.get(
            url, QUERY_STRING='has_status_filter=1&status_filter=completed'
        ).content.decode()
        # Use log-{id} marker which only appears in rendered run rows
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' not in content

    def test_no_filter_shows_all_statuses(self, client, forwarding_config):
        completed_run = ForwardingRun.objects.create(
            forwarding_config=forwarding_config,
            status=ForwardingRun.Status.COMPLETED,
        )
        failed_run = ForwardingRun.objects.create(
            forwarding_config=forwarding_config,
            status=ForwardingRun.Status.FAILED,
        )
        url = reverse('forwarding:run_history_table', args=[forwarding_config.id])
        content = client.get(url).content.decode()
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' in content

    def test_empty_filter_shows_nothing(self, client, forwarding_config):
        run = ForwardingRun.objects.create(
            forwarding_config=forwarding_config,
            status=ForwardingRun.Status.COMPLETED,
        )
        url = reverse('forwarding:run_history_table', args=[forwarding_config.id])
        content = client.get(url, QUERY_STRING='has_status_filter=1').content.decode()
        assert f'log-{run.id}' not in content

    def test_pagination_default_10(self, client, forwarding_config):
        for _ in range(15):
            ForwardingRun.objects.create(
                forwarding_config=forwarding_config,
                status=ForwardingRun.Status.COMPLETED,
            )
        url = reverse('forwarding:run_history_table', args=[forwarding_config.id])
        response = client.get(url)
        assert response.status_code == 200
        assert 'pagination' in response.content.decode()
