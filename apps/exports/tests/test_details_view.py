import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
from apps.db.models import Database
from apps.exports.models import ExportConfig, ExportRun

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='detailsuser_exp', email='dexp@example.com', password='pass'
    )


@pytest.fixture
def client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def server(db):
    server, _ = CommCareServer.objects.get_or_create(url='https://www.commcarehq.org')
    return server


@pytest.fixture
def project(db, server):
    return CommCareProject.objects.create(server=server, domain='details-domain')


@pytest.fixture
def account(db, server, user):
    return CommCareAccount.objects.create(
        server=server, username='u@x.com', api_key='key', owner=user
    )


@pytest.fixture
def database(db):
    return Database.objects.create(
        name='TestDB',
        connection_string='postgresql://localhost/test',
    )


@pytest.fixture
def export_config(db, user, project, account, database):
    return ExportConfig.objects.create(
        name='Test Export',
        project=project,
        account=account,
        database=database,
    )


@pytest.mark.django_db
class TestExportDetailsSmoke:
    def test_returns_200(self, client, export_config):
        response = client.get(
            reverse('exports:export_details', args=[export_config.id])
        )
        assert response.status_code == 200

    def test_no_details_suffix_in_heading(self, client, export_config):
        response = client.get(
            reverse('exports:export_details', args=[export_config.id])
        )
        assert '- Details' not in response.content.decode()

    def test_run_history_section_present(self, client, export_config):
        response = client.get(
            reverse('exports:export_details', args=[export_config.id])
        )
        content = response.content.decode()
        assert 'Run History' in content
        assert 'id="run-table"' in content

    def test_schedule_column_present(self, client, export_config):
        response = client.get(
            reverse('exports:export_details', args=[export_config.id])
        )
        assert 'Schedule' in response.content.decode()

    def test_status_filter_dropdown_present(self, client, export_config):
        response = client.get(
            reverse('exports:export_details', args=[export_config.id])
        )
        content = response.content.decode()
        assert 'status-filter-form' in content
        assert 'has_status_filter' in content


@pytest.mark.django_db
class TestExportRunHistoryTableEndpoint:
    def test_returns_200(self, client, export_config):
        url = reverse('exports:run_history_table', args=[export_config.id])
        assert client.get(url).status_code == 200

    def test_no_filter_shows_all_statuses(self, client, export_config):
        completed_run = ExportRun.objects.create(
            base_export_config=export_config, status=ExportRun.Status.COMPLETED
        )
        failed_run = ExportRun.objects.create(
            base_export_config=export_config, status=ExportRun.Status.FAILED
        )
        url = reverse('exports:run_history_table', args=[export_config.id])
        content = client.get(url).content.decode()
        # Use log-{id} marker which only appears in rendered run rows
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' in content

    def test_status_filter_excludes_unchecked(self, client, export_config):
        completed_run = ExportRun.objects.create(
            base_export_config=export_config, status=ExportRun.Status.COMPLETED
        )
        failed_run = ExportRun.objects.create(
            base_export_config=export_config, status=ExportRun.Status.FAILED
        )
        url = reverse('exports:run_history_table', args=[export_config.id])
        content = client.get(
            url,
            QUERY_STRING='has_status_filter=1&status_filter=completed',
        ).content.decode()
        # Use log-{id} marker which only appears in rendered run rows
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' not in content

    def test_empty_filter_shows_nothing(self, client, export_config):
        run = ExportRun.objects.create(
            base_export_config=export_config, status=ExportRun.Status.COMPLETED
        )
        url = reverse('exports:run_history_table', args=[export_config.id])
        content = client.get(url, QUERY_STRING='has_status_filter=1').content.decode()
        # No status values sent → no runs visible; use log-{id} marker which only
        # appears when a run row is rendered, not in URL paths.
        assert f'log-{run.id}' not in content

    def test_pagination_default_10(self, client, export_config):
        for _ in range(15):
            ExportRun.objects.create(
                base_export_config=export_config, status=ExportRun.Status.COMPLETED
            )
        url = reverse('exports:run_history_table', args=[export_config.id])
        response = client.get(url)
        assert response.status_code == 200
        # Pagination controls should appear when there are > 10 runs
        assert 'pagination' in response.content.decode()
