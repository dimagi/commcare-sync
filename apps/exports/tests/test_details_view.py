from django.urls import reverse
from unmagic import use

from apps.exports.models import ExportRun
from apps.exports.tests.fixtures import export_config_db_fixture
from tests.fixtures import authed_client, htmx_client


class TestExportDetailsSmoke:
    @use(authed_client, export_config_db_fixture)
    def test_returns_200(self):
        response = authed_client().get(
            reverse(
                'exports:export_details', args=[export_config_db_fixture().id]
            )
        )
        assert response.status_code == 200

    @use(authed_client, export_config_db_fixture)
    def test_no_details_suffix_in_heading(self):
        response = authed_client().get(
            reverse(
                'exports:export_details', args=[export_config_db_fixture().id]
            )
        )
        assert '- Details' not in response.content.decode()

    @use(authed_client, export_config_db_fixture)
    def test_run_history_section_present(self):
        response = authed_client().get(
            reverse(
                'exports:export_details', args=[export_config_db_fixture().id]
            )
        )
        content = response.content.decode()
        assert 'Run History' in content
        assert 'id="run-table"' in content

    @use(authed_client, export_config_db_fixture)
    def test_schedule_column_present(self):
        response = authed_client().get(
            reverse(
                'exports:export_details', args=[export_config_db_fixture().id]
            )
        )
        assert 'Schedule' in response.content.decode()

    @use(authed_client, export_config_db_fixture)
    def test_status_filter_dropdown_present(self):
        response = authed_client().get(
            reverse(
                'exports:export_details', args=[export_config_db_fixture().id]
            )
        )
        content = response.content.decode()
        assert 'status-filter-form' in content
        assert 'has_status_filter' in content


class TestExportRunHistoryTableEndpoint:
    @use(htmx_client, export_config_db_fixture)
    def test_returns_200(self):
        url = reverse(
            'exports:run_history_table', args=[export_config_db_fixture().id]
        )
        assert htmx_client().get(url).status_code == 200

    @use(authed_client, export_config_db_fixture)
    def test_non_htmx_request_rejected(self):
        url = reverse(
            'exports:run_history_table', args=[export_config_db_fixture().id]
        )
        assert authed_client().get(url).status_code == 400

    @use(htmx_client, export_config_db_fixture)
    def test_status_filter_excludes_unchecked(self):
        config = export_config_db_fixture()
        completed_run = ExportRun.objects.create(
            base_export_config=config, status=ExportRun.Status.COMPLETED
        )
        failed_run = ExportRun.objects.create(
            base_export_config=config, status=ExportRun.Status.FAILED
        )
        url = reverse('exports:run_history_table', args=[config.id])
        content = (
            htmx_client()
            .get(url, QUERY_STRING='status_filter=completed')
            .content.decode()
        )
        # Use log-{id} marker which only appears in rendered run rows
        assert f'log-{completed_run.id}' in content
        assert f'log-{failed_run.id}' not in content

    @use(htmx_client, export_config_db_fixture)
    def test_empty_filter_shows_nothing(self):
        config = export_config_db_fixture()
        run = ExportRun.objects.create(
            base_export_config=config, status=ExportRun.Status.COMPLETED
        )
        url = reverse('exports:run_history_table', args=[config.id])
        content = htmx_client().get(url).content.decode()
        # No status values sent → no runs visible; use log-{id} marker which only
        # appears when a run row is rendered, not in URL paths.
        assert f'log-{run.id}' not in content

    @use(htmx_client, export_config_db_fixture)
    def test_pagination_default_10(self):
        config = export_config_db_fixture()
        for _ in range(15):
            ExportRun.objects.create(
                base_export_config=config, status=ExportRun.Status.COMPLETED
            )
        url = reverse('exports:run_history_table', args=[config.id])
        response = htmx_client().get(
            url,
            QUERY_STRING='status_filter=completed',
        )
        assert response.status_code == 200
        # Pagination controls should appear when there are > 10 runs
        assert 'pagination' in response.content.decode()
