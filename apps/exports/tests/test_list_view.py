import re

from django.urls import reverse
from unmagic import fixture, use

from apps.exports.models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)
from tests.fixtures import (
    authed_client,
    commcare_account,
    commcare_project,
    database,
)


@fixture
@use('db')
def export_config():
    yield ExportConfig.objects.create(
        name='Test Export Config',
        project=commcare_project(),
        account=commcare_account(),
        database=database(),
    )


@fixture
@use('db')
def multi_export_config():
    yield MultiProjectExportConfig.objects.create(
        name='Multi Export Config',
        account=commcare_account(),
        database=database(),
    )


@fixture
@use('db')
def export_run():
    yield ExportRun.objects.create(
        base_export_config=export_config(),
        status=ExportRun.Status.COMPLETED,
    )


@fixture
@use('db')
def multi_export_run():
    yield MultiProjectExportRun.objects.create(
        base_export_config=multi_export_config(),
        status=MultiProjectExportRun.Status.COMPLETED,
    )


class TestExportConfigBaseProperties:
    @use(export_config)
    def test_export_config_edit_url(self):
        config = export_config()
        expected = reverse('exports:edit_export_config', args=[config.id])
        assert config.edit_url == expected

    @use(multi_export_config)
    def test_multi_export_config_edit_url(self):
        config = multi_export_config()
        expected = reverse(
            'exports:edit_multi_export_config', args=[config.id]
        )
        assert config.edit_url == expected

    @use(export_config)
    def test_last_run_log_url_none_when_no_run(self):
        assert export_config().last_run_log_url is None

    @use(multi_export_config)
    def test_last_run_log_url_none_when_no_run_multi(self):
        assert multi_export_config().last_run_log_url is None


class TestExportsHomeView:
    @use(authed_client)
    def test_stats_in_context(self):
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        assert 'export_stats' in response.context
        assert 'refresh_stats' in response.context
        assert 'forwarding_stats' in response.context

    @use(authed_client, export_config)
    def test_export_appears_in_list(self):
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        assert export_config().name in response.content.decode()


class TestConfigTableView:
    @use(authed_client)
    def test_requires_login(self):
        client = authed_client()
        client.logout()
        response = client.get(reverse('exports:config_table'))
        assert response.status_code == 302

    @use(authed_client)
    def test_returns_200(self):
        response = authed_client().get(reverse('exports:config_table'))
        assert response.status_code == 200

    @use(authed_client, export_config)
    def test_config_appears(self):
        response = authed_client().get(reverse('exports:config_table'))
        assert export_config().name in response.content.decode()

    @use(authed_client, commcare_project, commcare_account, database)
    def test_pagination_default_page_size_10(self):
        proj = commcare_project()
        acct = commcare_account()
        db_ = database()
        for i in range(15):
            ExportConfig.objects.create(
                name=f'Config {i}',
                project=proj,
                account=acct,
                database=db_,
            )
        response = authed_client().get(reverse('exports:config_table'))
        assert response.status_code == 200
        shown = response.content.decode().count('Config ')
        assert shown == 10

    @use(authed_client, commcare_project, commcare_account, database)
    def test_page_size_param_respected(self):
        proj = commcare_project()
        acct = commcare_account()
        db_ = database()
        for i in range(25):
            ExportConfig.objects.create(
                name=f'Config {i}',
                project=proj,
                account=acct,
                database=db_,
            )
        response = authed_client().get(
            reverse('exports:config_table'), {'page_size': 20}
        )
        assert response.status_code == 200
        shown = response.content.decode().count('Config ')
        assert shown == 20

    @use(authed_client, export_config)
    def test_etag_match_returns_no_swap(self):
        export_config()
        client = authed_client()
        # First request — get a valid etag
        response = client.get(reverse('exports:config_table'))
        assert response.status_code == 200
        match = re.search(
            r'data-etag="([a-f0-9]+)"', response.content.decode()
        )
        assert match, 'data-etag not found in response'
        etag = match.group(1)

        # Second request with matching etag — should return HX-Reswap: none
        response2 = client.get(
            reverse('exports:config_table'), {'etag': etag}
        )
        assert response2.status_code == 200
        assert response2.get('HX-Reswap') == 'none'

    @use(authed_client, export_config)
    def test_etag_mismatch_returns_full_content(self):
        config = export_config()
        response = authed_client().get(
            reverse('exports:config_table'), {'etag': 'stale'}
        )
        assert response.status_code == 200
        assert response.get('HX-Reswap') is None
        assert config.name in response.content.decode()

    @use(authed_client, export_config)
    def test_page_clamped_when_out_of_range(self):
        export_config()
        response = authed_client().get(
            reverse('exports:config_table'), {'page': 999}
        )
        assert response.status_code == 200


class TestRunLogView:
    @use(authed_client, export_run)
    def test_requires_login(self):
        run = export_run()
        client = authed_client()
        client.logout()
        response = client.get(reverse('exports:run_log', args=[run.id]))
        assert response.status_code == 302

    @use(authed_client, export_run)
    def test_returns_log_content(self):
        run = export_run()
        run.log = 'Test log output'
        run.save()
        response = authed_client().get(
            reverse('exports:run_log', args=[run.id])
        )
        assert response.status_code == 200
        assert 'Test log output' in response.content.decode()

    @use(authed_client)
    def test_404_for_invalid_run(self):
        response = authed_client().get(reverse('exports:run_log', args=[9999]))
        assert response.status_code == 404


class TestMultiRunLogView:
    @use(authed_client, multi_export_run)
    def test_requires_login(self):
        run = multi_export_run()
        client = authed_client()
        client.logout()
        response = client.get(reverse('exports:multi_run_log', args=[run.id]))
        assert response.status_code == 302

    @use(authed_client, multi_export_run)
    def test_returns_log_content(self):
        run = multi_export_run()
        run.log = 'Multi log output'
        run.save()
        response = authed_client().get(
            reverse('exports:multi_run_log', args=[run.id])
        )
        assert response.status_code == 200
        assert 'Multi log output' in response.content.decode()


class TestExportsHomeViewUpdated:
    @use(authed_client)
    def test_home_includes_config_table_div(self):
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        assert 'id="exports-config-table"' in response.content.decode()

    @use(authed_client, multi_export_config)
    def test_multi_config_appears_in_merged_table(self):
        config = multi_export_config()
        response = authed_client().get(reverse('exports:home'))
        assert config.name in response.content.decode()


class TestExportConfigHasActiveRun:
    @use(export_config)
    def test_false_with_no_runs(self):
        assert export_config().has_active_run is False

    @use(export_config)
    def test_false_when_run_is_completed(self):
        config = export_config()
        ExportRun.objects.create(
            base_export_config=config,
            status=ExportRun.Status.COMPLETED,
        )
        assert config.has_active_run is False

    @use(export_config)
    def test_false_when_run_is_failed(self):
        config = export_config()
        ExportRun.objects.create(
            base_export_config=config,
            status=ExportRun.Status.FAILED,
        )
        assert config.has_active_run is False

    @use(export_config)
    def test_true_when_run_is_queued(self):
        config = export_config()
        ExportRun.objects.create(
            base_export_config=config,
            status=ExportRun.Status.QUEUED,
        )
        assert config.has_active_run is True

    @use(export_config)
    def test_true_when_run_is_started(self):
        config = export_config()
        ExportRun.objects.create(
            base_export_config=config,
            status=ExportRun.Status.STARTED,
        )
        assert config.has_active_run is True

    @use(export_config)
    def test_uses_prefetched_runs_without_db_query(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        config = export_config()
        run = ExportRun.objects.create(
            base_export_config=config,
            status=ExportRun.Status.QUEUED,
        )
        config._all_runs = [run]
        with CaptureQueriesContext(connection) as ctx:
            result = config.has_active_run
        assert len(ctx) == 0
        assert result is True


class TestIsMultiProject:
    @use(export_config)
    def test_export_config_is_not_multi_project(self):
        assert export_config().is_multi_project is False

    @use(multi_export_config)
    def test_multi_export_config_is_multi_project(self):
        assert multi_export_config().is_multi_project is True


class TestRunExportHtmxBranch:
    @use(authed_client, export_config)
    def test_htmx_request_returns_204(self):
        url = reverse('exports:run_export', args=[export_config().id])
        response = authed_client().post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    @use(authed_client, export_config)
    def test_htmx_request_creates_export_run(self):
        config = export_config()
        url = reverse('exports:run_export', args=[config.id])
        authed_client().post(url, HTTP_HX_REQUEST='true')
        assert ExportRun.objects.filter(
            base_export_config=config,
            triggered_from_ui=True,
        ).exists()

    @use(authed_client, export_config)
    def test_non_htmx_request_returns_200_with_task_id(self):
        import json
        url = reverse('exports:run_export', args=[export_config().id])
        response = authed_client().post(
            url,
            data=json.dumps({'forceSync': False}),
            content_type='application/json',
        )
        assert response.status_code == 200
        assert len(response.content) > 0  # task ID in body

    @use(authed_client, export_config)
    def test_non_htmx_force_sync_true_passes_flag(self):
        """forceSync: true in JSON body passes force_sync_all_data=True to task."""
        import json
        from unittest.mock import patch
        url = reverse('exports:run_export', args=[export_config().id])
        with patch('apps.exports.views.run_export_task') as mock_task:
            mock_task.delay.return_value.task_id = 'fake-id'
            authed_client().post(
                url,
                data=json.dumps({'forceSync': True}),
                content_type='application/json',
            )
        mock_task.delay.assert_called_once()
        _, kwargs = mock_task.delay.call_args
        assert kwargs['force_sync_all_data'] is True


class TestRunMultiExportHtmxBranch:
    @use(authed_client, multi_export_config)
    def test_htmx_request_returns_204(self):
        url = reverse(
            'exports:run_multi_export', args=[multi_export_config().id]
        )
        response = authed_client().post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    @use(authed_client, multi_export_config)
    def test_htmx_request_creates_multi_export_run(self):
        config = multi_export_config()
        url = reverse('exports:run_multi_export', args=[config.id])
        authed_client().post(url, HTTP_HX_REQUEST='true')
        assert MultiProjectExportRun.objects.filter(
            base_export_config=config,
            triggered_from_ui=True,
        ).exists()


class TestExportsHomeSmoke:
    """Smoke tests: full-page renders with configs in various run states."""

    @use(authed_client, export_config)
    def test_renders_with_no_runs(self):
        config = export_config()
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        assert config.name in response.content.decode()

    @use(authed_client, export_config)
    def test_renders_with_completed_run(self):
        config = export_config()
        ExportRun.objects.create(
            base_export_config=config,
            status=ExportRun.Status.COMPLETED,
            log='Exported 100 rows.',
        )
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        content = response.content.decode()
        assert config.name in content
        assert 'completed' in content

    @use(authed_client, export_config)
    def test_renders_with_failed_run(self):
        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.FAILED,
            log='Error: connection refused.',
        )
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        assert 'failed' in response.content.decode()

    @use(authed_client, export_config)
    def test_renders_with_started_run(self):
        ExportRun.objects.create(
            base_export_config=export_config(),
            status=ExportRun.Status.STARTED,
        )
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        assert 'started' in response.content.decode()

    @use(authed_client, multi_export_config)
    def test_renders_multi_config_with_completed_run(self):
        config = multi_export_config()
        MultiProjectExportRun.objects.create(
            base_export_config=config,
            status=MultiProjectExportRun.Status.COMPLETED,
        )
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        assert config.name in response.content.decode()

    @use(authed_client)
    def test_new_export_split_dropdown_present(self):
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'dropdown-toggle-split' in content
        assert 'Multi-Project Export' in content


class TestExportsRunButtonRendering:
    @use(authed_client, export_config)
    def test_run_button_present_when_no_active_run(self):
        config = export_config()
        url = reverse('exports:config_table')
        response = authed_client().get(url)
        assert response.status_code == 200
        content = response.content.decode()
        run_url = reverse('exports:run_export', args=[config.id])
        assert f'hx-post="{run_url}"' in content

    @use(authed_client, export_config)
    def test_run_button_disabled_when_active_run(self):
        config = export_config()
        ExportRun.objects.create(
            base_export_config=config,
            status=ExportRun.Status.QUEUED,
        )
        url = reverse('exports:config_table')
        response = authed_client().get(url)
        content = response.content.decode()
        # Run button present but disabled
        assert 'btn-outline-success' in content
        run_url = reverse('exports:run_export', args=[config.id])
        assert f'hx-post="{run_url}"' not in content  # disabled, no hx-post

    @use(authed_client, multi_export_config)
    def test_multi_export_run_button_uses_multi_url(self):
        config = multi_export_config()
        url = reverse('exports:config_table')
        response = authed_client().get(url)
        content = response.content.decode()
        run_url = reverse('exports:run_multi_export', args=[config.id])
        assert f'hx-post="{run_url}"' in content

    @use(authed_client, export_config)
    def test_edit_button_never_disabled(self):
        config = export_config()
        ExportRun.objects.create(
            base_export_config=config,
            status=ExportRun.Status.QUEUED,
        )
        url = reverse('exports:config_table')
        response = authed_client().get(url)
        content = response.content.decode()
        edit_url = config.edit_url
        assert edit_url in content
