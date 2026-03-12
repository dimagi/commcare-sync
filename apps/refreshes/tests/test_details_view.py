import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.exports.models import ExportDatabase
from apps.refreshes.models import RefreshConfig, RefreshRun

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='detailsuser_ref', email='dref@example.com', password='pass'
    )


@pytest.fixture
def client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def database(db, user):
    return ExportDatabase.objects.create(
        name='TestDB',
        connection_string='postgresql://localhost/test',
        owner=user,
    )


@pytest.fixture
def refresh_config(db, user, database):
    return RefreshConfig.objects.create(
        name='Test Refresh',
        database=database,
        materialized_views=['public.mv_test'],
        created_by=user,
    )


@pytest.mark.django_db
class TestRefreshDetailsSmoke:
    def test_returns_200(self, client, refresh_config):
        response = client.get(
            reverse('refreshes:refresh_details', args=[refresh_config.id])
        )
        assert response.status_code == 200

    def test_no_details_suffix_in_heading(self, client, refresh_config):
        response = client.get(
            reverse('refreshes:refresh_details', args=[refresh_config.id])
        )
        assert '- Details' not in response.content.decode()

    def test_run_table_present(self, client, refresh_config):
        response = client.get(
            reverse('refreshes:refresh_details', args=[refresh_config.id])
        )
        assert 'id="run-table"' in response.content.decode()

    def test_status_filter_dropdown_present(self, client, refresh_config):
        response = client.get(
            reverse('refreshes:refresh_details', args=[refresh_config.id])
        )
        content = response.content.decode()
        assert 'status-filter-form' in content
        assert 'has_status_filter' in content

    def test_run_history_section_present(self, client, refresh_config):
        response = client.get(
            reverse('refreshes:refresh_details', args=[refresh_config.id])
        )
        content = response.content.decode()
        assert 'Run History' in content
        assert 'id="run-table"' in content

    def test_schedule_column_present(self, client, refresh_config):
        response = client.get(
            reverse('refreshes:refresh_details', args=[refresh_config.id])
        )
        assert 'Schedule' in response.content.decode()


@pytest.mark.django_db
class TestRefreshRunHistoryTableEndpoint:
    def test_returns_200(self, client, refresh_config):
        assert (
            client.get(
                reverse('refreshes:run_history_table', args=[refresh_config.id])
            ).status_code
            == 200
        )

    def test_status_filter_excludes_unchecked(self, client, refresh_config):
        completed_run = RefreshRun.objects.create(
            refresh_config=refresh_config, status=RefreshRun.Status.COMPLETED
        )
        failed_run = RefreshRun.objects.create(
            refresh_config=refresh_config, status=RefreshRun.Status.FAILED
        )
        url = reverse('refreshes:run_history_table', args=[refresh_config.id])
        content = client.get(
            url, QUERY_STRING='has_status_filter=1&status_filter=completed'
        ).content.decode()
        # Use log-{id} marker which only appears in rendered run rows
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' not in content

    def test_no_filter_shows_all_statuses(self, client, refresh_config):
        completed_run = RefreshRun.objects.create(
            refresh_config=refresh_config, status=RefreshRun.Status.COMPLETED
        )
        failed_run = RefreshRun.objects.create(
            refresh_config=refresh_config, status=RefreshRun.Status.FAILED
        )
        url = reverse('refreshes:run_history_table', args=[refresh_config.id])
        content = client.get(url).content.decode()
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' in content

    def test_empty_filter_shows_nothing(self, client, refresh_config):
        run = RefreshRun.objects.create(
            refresh_config=refresh_config, status=RefreshRun.Status.COMPLETED
        )
        url = reverse('refreshes:run_history_table', args=[refresh_config.id])
        content = client.get(url, QUERY_STRING='has_status_filter=1').content.decode()
        assert f'log-{run.id}' not in content

    def test_pagination_default_10(self, client, refresh_config):
        for _ in range(15):
            RefreshRun.objects.create(
                refresh_config=refresh_config, status=RefreshRun.Status.COMPLETED
            )
        url = reverse('refreshes:run_history_table', args=[refresh_config.id])
        response = client.get(url)
        assert response.status_code == 200
        assert 'pagination' in response.content.decode()
