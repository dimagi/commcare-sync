from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

from apps.db.models import Database
from apps.refreshes.models import RefreshConfig, RefreshRun

User = get_user_model()


@fixture
@use('db')
def user():
    yield User.objects.create_user(
        username='detailsuser_ref', email='dref@example.com', password='pass'
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
        name='TestDB',
        connection_string='postgresql://localhost/test',
    )


@fixture
def refresh_config():
    yield RefreshConfig.objects.create(
        name='Test Refresh',
        database=database(),
        materialized_views=['public.mv_test'],
    )


class TestRefreshDetailsSmoke:
    @use(authed_client, refresh_config)
    def test_returns_200(self):
        response = authed_client().get(
            reverse('refreshes:refresh_details', args=[refresh_config().id])
        )
        assert response.status_code == 200

    @use(authed_client, refresh_config)
    def test_no_details_suffix_in_heading(self):
        response = authed_client().get(
            reverse('refreshes:refresh_details', args=[refresh_config().id])
        )
        assert '- Details' not in response.content.decode()

    @use(authed_client, refresh_config)
    def test_run_table_present(self):
        response = authed_client().get(
            reverse('refreshes:refresh_details', args=[refresh_config().id])
        )
        assert 'id="run-table"' in response.content.decode()

    @use(authed_client, refresh_config)
    def test_status_filter_dropdown_present(self):
        response = authed_client().get(
            reverse('refreshes:refresh_details', args=[refresh_config().id])
        )
        content = response.content.decode()
        assert 'status-filter-form' in content
        assert 'has_status_filter' in content


class TestRefreshRunHistoryTableEndpoint:
    @use(authed_client, refresh_config)
    def test_returns_200(self):
        assert (
            authed_client()
            .get(
                reverse('refreshes:run_history_table', args=[refresh_config().id])
            )
            .status_code
            == 200
        )

    @use(authed_client, refresh_config)
    def test_status_filter_works(self):
        config = refresh_config()
        completed_run = RefreshRun.objects.create(
            refresh_config=config, status=RefreshRun.Status.COMPLETED
        )
        failed_run = RefreshRun.objects.create(
            refresh_config=config, status=RefreshRun.Status.FAILED
        )
        url = reverse('refreshes:run_history_table', args=[config.id])
        content = authed_client().get(
            url, QUERY_STRING='has_status_filter=1&status_filter=completed'
        ).content.decode()
        # Use log-{id} marker which only appears in rendered run rows
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' not in content

    @use(authed_client, refresh_config)
    def test_no_filter_shows_all_statuses(self):
        config = refresh_config()
        completed_run = RefreshRun.objects.create(
            refresh_config=config, status=RefreshRun.Status.COMPLETED
        )
        failed_run = RefreshRun.objects.create(
            refresh_config=config, status=RefreshRun.Status.FAILED
        )
        url = reverse('refreshes:run_history_table', args=[config.id])
        content = authed_client().get(url).content.decode()
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' in content

    @use(authed_client, refresh_config)
    def test_empty_filter_shows_nothing(self):
        config = refresh_config()
        run = RefreshRun.objects.create(
            refresh_config=config, status=RefreshRun.Status.COMPLETED
        )
        url = reverse('refreshes:run_history_table', args=[config.id])
        content = authed_client().get(
            url, QUERY_STRING='has_status_filter=1'
        ).content.decode()
        assert f'log-{run.id}' not in content
