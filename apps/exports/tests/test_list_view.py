import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.commcare.models import (
    CommCareAccount,
    CommCareProject,
    CommCareServer,
)
from apps.db.models import Database
from apps.exports.models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='listviewuser', email='lv@example.com', password='pass'
    )


@pytest.fixture
def client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def server(db):
    server, _ = CommCareServer.objects.get_or_create(
        url='https://www.commcarehq.org'
    )
    return server


@pytest.fixture
def project(db, server):
    return CommCareProject.objects.create(server=server, domain='test-domain')


@pytest.fixture
def account(db, server, user):
    return CommCareAccount.objects.create(
        server=server, username='u@example.com', api_key='key', owner=user
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
        name='Test Export Config',
        project=project,
        account=account,
        database=database,
    )


@pytest.fixture
def multi_export_config(db, user, account, database):
    config = MultiProjectExportConfig.objects.create(
        name='Multi Export Config',
        account=account,
        database=database,
    )
    return config


@pytest.fixture
def export_run(db, export_config):
    return ExportRun.objects.create(
        base_export_config=export_config,
        status=ExportRun.Status.COMPLETED,
    )


@pytest.fixture
def multi_export_run(db, multi_export_config):
    return MultiProjectExportRun.objects.create(
        base_export_config=multi_export_config,
        status=MultiProjectExportRun.Status.COMPLETED,
    )


class TestExportConfigBaseProperties:
    def test_export_config_edit_url(self, export_config):
        expected = reverse(
            'exports:edit_export_config', args=[export_config.id]
        )
        assert export_config.edit_url == expected

    def test_multi_export_config_edit_url(self, multi_export_config):
        expected = reverse(
            'exports:edit_multi_export_config', args=[multi_export_config.id]
        )
        assert multi_export_config.edit_url == expected

    def test_last_run_log_url_none_when_no_run(self, export_config):
        assert export_config.last_run_log_url is None

    def test_last_run_log_url_none_when_no_run_multi(
        self, multi_export_config
    ):
        assert multi_export_config.last_run_log_url is None


class TestExportsHomeView:
    def test_stats_in_context(self, client, db):
        url = reverse('exports:home')
        response = client.get(url)
        assert response.status_code == 200
        assert 'export_stats' in response.context
        assert 'refresh_stats' in response.context
        assert 'forwarding_stats' in response.context

    def test_export_appears_in_list(self, client, export_config):
        url = reverse('exports:home')
        response = client.get(url)
        assert response.status_code == 200
        assert export_config.name in response.content.decode()


class TestConfigTableView:
    def test_requires_login(self, client, user):
        client.logout()
        url = reverse('exports:config_table')
        response = client.get(url)
        assert response.status_code == 302

    def test_returns_200(self, client, db):
        url = reverse('exports:config_table')
        response = client.get(url)
        assert response.status_code == 200

    def test_config_appears(self, client, export_config):
        url = reverse('exports:config_table')
        response = client.get(url)
        assert export_config.name in response.content.decode()

    def test_pagination_default_page_size_10(
        self, client, user, project, account, database
    ):
        for i in range(15):
            ExportConfig.objects.create(
                name=f'Config {i}',
                project=project,
                account=account,
                database=database,
            )
        response = client.get(reverse('exports:config_table'))
        assert response.status_code == 200
        content = response.content.decode()
        # Only 10 of the 15 configs should appear
        shown = content.count('Config ')
        assert shown == 10

    def test_page_size_param_respected(
        self, client, user, project, account, database
    ):
        for i in range(25):
            ExportConfig.objects.create(
                name=f'Config {i}',
                project=project,
                account=account,
                database=database,
            )
        response = client.get(
            reverse('exports:config_table'), {'page_size': 20}
        )
        assert response.status_code == 200
        shown = response.content.decode().count('Config ')
        assert shown == 20

    def test_etag_match_returns_no_swap(self, client, export_config):
        # First request — get a valid etag
        response = client.get(reverse('exports:config_table'))
        assert response.status_code == 200
        content = response.content.decode()
        # Extract etag from data-etag attribute
        import re

        match = re.search(r'data-etag="([a-f0-9]+)"', content)
        assert match, 'data-etag not found in response'
        etag = match.group(1)

        # Second request with matching etag — should return HX-Reswap: none
        response2 = client.get(reverse('exports:config_table'), {'etag': etag})
        assert response2.status_code == 200
        assert response2.get('HX-Reswap') == 'none'

    def test_etag_mismatch_returns_full_content(self, client, export_config):
        response = client.get(
            reverse('exports:config_table'), {'etag': 'stale'}
        )
        assert response.status_code == 200
        assert response.get('HX-Reswap') is None
        assert export_config.name in response.content.decode()

    def test_page_clamped_when_out_of_range(self, client, export_config):
        response = client.get(reverse('exports:config_table'), {'page': 999})
        assert response.status_code == 200


class TestRunLogView:
    def test_requires_login(self, client, user, export_run):
        client.logout()
        response = client.get(reverse('exports:run_log', args=[export_run.id]))
        assert response.status_code == 302

    def test_returns_log_content(self, client, export_run):
        export_run.log = 'Test log output'
        export_run.save()
        response = client.get(reverse('exports:run_log', args=[export_run.id]))
        assert response.status_code == 200
        assert 'Test log output' in response.content.decode()

    def test_404_for_invalid_run(self, client):
        response = client.get(reverse('exports:run_log', args=[9999]))
        assert response.status_code == 404


class TestMultiRunLogView:
    def test_requires_login(self, client, user, multi_export_run):
        client.logout()
        response = client.get(reverse('exports:multi_run_log', args=[multi_export_run.id]))
        assert response.status_code == 302

    def test_returns_log_content(self, client, multi_export_run):
        multi_export_run.log = 'Multi log output'
        multi_export_run.save()
        response = client.get(
            reverse('exports:multi_run_log', args=[multi_export_run.id])
        )
        assert response.status_code == 200
        assert 'Multi log output' in response.content.decode()


class TestExportsHomeViewUpdated:
    def test_home_includes_config_table_div(self, client, db):
        response = client.get(reverse('exports:home'))
        assert response.status_code == 200
        assert 'id="exports-config-table"' in response.content.decode()

    def test_multi_config_appears_in_merged_table(self, client, multi_export_config):
        response = client.get(reverse('exports:home'))
        assert multi_export_config.name in response.content.decode()


@pytest.mark.django_db
class TestExportConfigHasActiveRun:
    def test_false_with_no_runs(self, export_config):
        assert export_config.has_active_run is False

    def test_false_when_run_is_completed(self, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.COMPLETED,
        )
        assert export_config.has_active_run is False

    def test_false_when_run_is_failed(self, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.FAILED,
        )
        assert export_config.has_active_run is False

    def test_true_when_run_is_queued(self, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.QUEUED,
        )
        assert export_config.has_active_run is True

    def test_true_when_run_is_started(self, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.STARTED,
        )
        assert export_config.has_active_run is True

    def test_uses_prefetched_runs_without_db_query(self, export_config):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        run = ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.QUEUED,
        )
        export_config._all_runs = [run]
        with CaptureQueriesContext(connection) as ctx:
            result = export_config.has_active_run
        assert len(ctx) == 0
        assert result is True


@pytest.mark.django_db
class TestIsMultiProject:
    def test_export_config_is_not_multi_project(self, export_config):
        assert export_config.is_multi_project is False

    def test_multi_export_config_is_multi_project(self, multi_export_config):
        assert multi_export_config.is_multi_project is True


@pytest.mark.django_db
class TestRunExportHtmxBranch:
    def test_htmx_request_returns_204(self, client, export_config):
        url = reverse('exports:run_export', args=[export_config.id])
        response = client.post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    def test_htmx_request_creates_export_run(self, client, export_config):
        url = reverse('exports:run_export', args=[export_config.id])
        client.post(url, HTTP_HX_REQUEST='true')
        assert ExportRun.objects.filter(
            base_export_config=export_config,
            triggered_from_ui=True,
        ).exists()

    def test_non_htmx_request_returns_200_with_task_id(
        self, client, export_config
    ):
        import json
        url = reverse('exports:run_export', args=[export_config.id])
        response = client.post(
            url,
            data=json.dumps({'forceSync': False}),
            content_type='application/json',
        )
        assert response.status_code == 200
        assert len(response.content) > 0  # task ID in body

    def test_non_htmx_force_sync_true_passes_flag(
        self, client, export_config
    ):
        """forceSync: true in JSON body passes force_sync_all_data=True to task."""
        import json
        from unittest.mock import patch
        url = reverse('exports:run_export', args=[export_config.id])
        with patch('apps.exports.views.run_export_task') as mock_task:
            mock_task.delay.return_value.task_id = 'fake-id'
            client.post(
                url,
                data=json.dumps({'forceSync': True}),
                content_type='application/json',
            )
        mock_task.delay.assert_called_once()
        _, kwargs = mock_task.delay.call_args
        assert kwargs['force_sync_all_data'] is True


@pytest.mark.django_db
class TestRunMultiExportHtmxBranch:
    def test_htmx_request_returns_204(self, client, multi_export_config):
        url = reverse('exports:run_multi_export', args=[multi_export_config.id])
        response = client.post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    def test_htmx_request_creates_multi_export_run(
        self, client, multi_export_config
    ):
        url = reverse('exports:run_multi_export', args=[multi_export_config.id])
        client.post(url, HTTP_HX_REQUEST='true')
        assert MultiProjectExportRun.objects.filter(
            base_export_config=multi_export_config,
            triggered_from_ui=True,
        ).exists()


@pytest.mark.django_db
class TestExportsHomeSmoke:
    """Smoke tests: full-page renders with configs in various run states."""

    def test_renders_with_no_runs(self, client, export_config):
        """Template handles configs with no runs (Never / — paths)."""
        response = client.get(reverse('exports:home'))
        assert response.status_code == 200
        assert export_config.name in response.content.decode()

    def test_renders_with_completed_run(self, client, export_config):
        """Template handles completed run: status icon, log button enabled, duration."""
        run = ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.COMPLETED,
            log='Exported 100 rows.',
        )
        response = client.get(reverse('exports:home'))
        assert response.status_code == 200
        content = response.content.decode()
        assert export_config.name in content
        assert 'completed' in content

    def test_renders_with_failed_run(self, client, export_config):
        """Template handles failed run: log button enabled."""
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.FAILED,
            log='Error: connection refused.',
        )
        response = client.get(reverse('exports:home'))
        assert response.status_code == 200
        assert 'failed' in response.content.decode()

    def test_renders_with_started_run(self, client, export_config):
        """Template handles in-progress run: log button disabled."""
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.STARTED,
        )
        response = client.get(reverse('exports:home'))
        assert response.status_code == 200
        assert 'started' in response.content.decode()

    def test_renders_multi_config_with_completed_run(self, client, multi_export_config):
        """Template handles multi-project config with a completed run."""
        run = MultiProjectExportRun.objects.create(
            base_export_config=multi_export_config,
            status=MultiProjectExportRun.Status.COMPLETED,
        )
        response = client.get(reverse('exports:home'))
        assert response.status_code == 200
        assert multi_export_config.name in response.content.decode()

    def test_new_export_split_dropdown_present(self, client, db):
        """Split dropdown for New Export / Multi-Project Export is rendered."""
        response = client.get(reverse('exports:home'))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'dropdown-toggle-split' in content
        assert 'Multi-Project Export' in content


@pytest.mark.django_db
class TestExportsRunButtonRendering:
    def test_run_button_present_when_no_active_run(
        self, client, export_config
    ):
        url = reverse('exports:config_table')
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        run_url = reverse('exports:run_export', args=[export_config.id])
        assert f'hx-post="{run_url}"' in content

    def test_run_button_disabled_when_active_run(self, client, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.QUEUED,
        )
        url = reverse('exports:config_table')
        response = client.get(url)
        content = response.content.decode()
        # Run button present but disabled
        assert 'btn-outline-success' in content
        run_url = reverse('exports:run_export', args=[export_config.id])
        assert f'hx-post="{run_url}"' not in content  # disabled, no hx-post

    def test_multi_export_run_button_uses_multi_url(
        self, client, multi_export_config
    ):
        url = reverse('exports:config_table')
        response = client.get(url)
        content = response.content.decode()
        run_url = reverse(
            'exports:run_multi_export', args=[multi_export_config.id]
        )
        assert f'hx-post="{run_url}"' in content

    def test_edit_button_never_disabled(self, client, export_config):
        ExportRun.objects.create(
            base_export_config=export_config,
            status=ExportRun.Status.QUEUED,
        )
        url = reverse('exports:config_table')
        response = client.get(url)
        content = response.content.decode()
        edit_url = export_config.edit_url
        assert edit_url in content
