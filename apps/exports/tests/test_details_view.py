from django.test import Client
from django.urls import reverse
from unmagic import fixture, use

from apps.commcare.models import CommCareAccount, CommCareProject, CommCareServer
from apps.exports.models import ExportConfig, ExportRun
from tests.fixtures import database, user


@fixture
def authed_client():
    client = Client()
    client.force_login(user())
    yield client


@fixture
@use('db')
def server():
    server, _ = CommCareServer.objects.get_or_create(
        url='https://www.commcarehq.org'
    )
    yield server


@fixture
def project():
    yield CommCareProject.objects.create(
        server=server(), domain='details-domain'
    )


@fixture
def account():
    yield CommCareAccount.objects.create(
        server=server(), username='u@x.com', api_key='key', owner=user()
    )


@fixture
def export_config():
    yield ExportConfig.objects.create(
        name='Test Export',
        project=project(),
        account=account(),
        database=database(),
    )


class TestExportDetailsSmoke:
    @use(authed_client, export_config)
    def test_returns_200(self):
        response = authed_client().get(
            reverse('exports:export_details', args=[export_config().id])
        )
        assert response.status_code == 200

    @use(authed_client, export_config)
    def test_no_details_suffix_in_heading(self):
        response = authed_client().get(
            reverse('exports:export_details', args=[export_config().id])
        )
        assert '- Details' not in response.content.decode()

    @use(authed_client, export_config)
    def test_run_history_section_present(self):
        response = authed_client().get(
            reverse('exports:export_details', args=[export_config().id])
        )
        content = response.content.decode()
        assert 'Run History' in content
        assert 'id="run-table"' in content

    @use(authed_client, export_config)
    def test_schedule_column_present(self):
        response = authed_client().get(
            reverse('exports:export_details', args=[export_config().id])
        )
        assert 'Schedule' in response.content.decode()

    @use(authed_client, export_config)
    def test_status_filter_dropdown_present(self):
        response = authed_client().get(
            reverse('exports:export_details', args=[export_config().id])
        )
        content = response.content.decode()
        assert 'status-filter-form' in content
        assert 'has_status_filter' in content


class TestExportRunHistoryTableEndpoint:
    @use(authed_client, export_config)
    def test_returns_200(self):
        url = reverse('exports:run_history_table', args=[export_config().id])
        assert authed_client().get(url).status_code == 200

    @use(authed_client, export_config)
    def test_no_filter_shows_all_statuses(self):
        config = export_config()
        completed_run = ExportRun.objects.create(
            base_export_config=config, status=ExportRun.Status.COMPLETED
        )
        failed_run = ExportRun.objects.create(
            base_export_config=config, status=ExportRun.Status.FAILED
        )
        url = reverse('exports:run_history_table', args=[config.id])
        content = authed_client().get(url).content.decode()
        # Use log-{id} marker which only appears in rendered run rows
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' in content

    @use(authed_client, export_config)
    def test_status_filter_excludes_unchecked(self):
        config = export_config()
        completed_run = ExportRun.objects.create(
            base_export_config=config, status=ExportRun.Status.COMPLETED
        )
        failed_run = ExportRun.objects.create(
            base_export_config=config, status=ExportRun.Status.FAILED
        )
        url = reverse('exports:run_history_table', args=[config.id])
        content = authed_client().get(
            url,
            QUERY_STRING='has_status_filter=1&status_filter=completed',
        ).content.decode()
        # Use log-{id} marker which only appears in rendered run rows
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' not in content

    @use(authed_client, export_config)
    def test_empty_filter_shows_nothing(self):
        config = export_config()
        run = ExportRun.objects.create(
            base_export_config=config, status=ExportRun.Status.COMPLETED
        )
        url = reverse('exports:run_history_table', args=[config.id])
        content = authed_client().get(
            url, QUERY_STRING='has_status_filter=1'
        ).content.decode()
        # No status values sent → no runs visible; use log-{id} marker which only
        # appears when a run row is rendered, not in URL paths.
        assert f'log-{run.id}' not in content

    @use(authed_client, export_config)
    def test_pagination_default_10(self):
        config = export_config()
        for _ in range(15):
            ExportRun.objects.create(
                base_export_config=config, status=ExportRun.Status.COMPLETED
            )
        url = reverse('exports:run_history_table', args=[config.id])
        response = authed_client().get(url)
        assert response.status_code == 200
        # Pagination controls should appear when there are > 10 runs
        assert 'pagination' in response.content.decode()
