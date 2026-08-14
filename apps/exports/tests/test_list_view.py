import re
from unittest.mock import patch

import pytest
from django.urls import reverse
from django_q.models import OrmQ
from unmagic import fixture, use

from apps.exports.models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportRun,
)
from apps.exports.tests.fixtures import (
    export_config,
    export_run,
    multi_export_config,
    multi_export_run,
)
from tests.fixtures import (
    authed_client,
    commcare_account,
    commcare_project,
    database,
)


@use(export_config)
class TestExportConfigProperties:
    def test_export_config_edit_url(self):
        config = export_config()
        expected = reverse('exports:edit_export_config', args=[config.id])
        assert config.edit_url == expected

    def test_last_run_log_url_none_when_no_run(self):
        assert export_config().last_run_log_url is None

    @use(export_run)
    def test_last_run_log_url_with_run(self):
        run = export_run()
        expected = reverse('exports:run_log', args=[run.id])
        assert export_config().last_run_log_url == expected


@use(multi_export_config)
class TestMultiExportConfigProperties:

    def test_multi_export_config_edit_url(self):
        config = multi_export_config()
        expected = reverse(
            'exports:edit_multi_export_config',
            args=[config.id],
        )
        assert config.edit_url == expected

    def test_last_run_log_url_none_when_no_run_multi(self):
        assert multi_export_config().last_run_log_url is None

    @use(multi_export_run)
    def test_last_run_log_url_with_run_multi(self):
        run = multi_export_run()
        expected = reverse('exports:multi_run_log', args=[run.id])
        assert multi_export_config().last_run_log_url == expected


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
            r'"etag":\s*"([a-f0-9]+)"', response.content.decode()
        )
        assert match, 'etag not found in hx-vals'
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


@fixture
def mock_async_task_dispatch():
    # Suppress dispatch so these view tests don't leave a live django-q
    # OrmQ row queued behind them (async_task's ORM broker really does
    # insert a row, even though nothing consumes it in tests). The view
    # now dispatches via apps.schedules.dispatch.create_run_and_dispatch,
    # which is where async_task is actually called from.
    with patch('apps.schedules.dispatch.async_task') as mock:
        mock.return_value = 'test-task-id'
        yield mock


@use(authed_client, export_config, mock_async_task_dispatch)
class TestRunExportHtmxBranch:
    def test_htmx_request_returns_204(self):
        url = reverse('exports:run_export', args=[export_config().id])
        response = authed_client().post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    def test_htmx_request_triggers_table_refresh(self):
        # The 204 carries HX-Trigger so the config table reloads and shows the
        # new run's real status right away.
        url = reverse('exports:run_export', args=[export_config().id])
        response = authed_client().post(url, HTTP_HX_REQUEST='true')
        assert response['HX-Trigger'] == 'runStarted'

    def test_htmx_request_creates_export_run(self):
        config = export_config()
        url = reverse('exports:run_export', args=[config.id])
        authed_client().post(url, HTTP_HX_REQUEST='true')
        assert ExportRun.objects.filter(
            config=config,
            triggered_from_ui=True,
        ).exists()
        assert OrmQ.objects.count() == 0

    def test_htmx_request_skips_when_active_run_exists(self):
        # Guards the double-submit window: a Run posted while a run is already
        # active must not stack a second run.
        config = export_config()
        ExportRun.objects.create(
            config=config,
            status=ExportRun.Status.STARTED,
        )
        url = reverse('exports:run_export', args=[config.id])
        response = authed_client().post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204
        assert ExportRun.objects.filter(config=config).count() == 1

    def test_non_htmx_request_returns_200_with_task_id(self):
        import json
        url = reverse('exports:run_export', args=[export_config().id])
        response = authed_client().post(
            url,
            data=json.dumps({'startOver': False}),
            content_type='application/json',
        )
        assert response.status_code == 200
        assert len(response.content) > 0  # task ID in body

    def test_non_htmx_start_over_true_passes_flag(self):
        """startOver: true in JSON body passes start_over=True to task."""
        import json
        url = reverse('exports:run_export', args=[export_config().id])
        with patch('apps.schedules.dispatch.async_task') as mock_async:
            mock_async.return_value = 'fake-id'
            authed_client().post(
                url,
                data=json.dumps({'startOver': True}),
                content_type='application/json',
            )
        mock_async.assert_called_once()
        _, kwargs = mock_async.call_args
        assert kwargs['start_over'] is True


@use(authed_client, multi_export_config, mock_async_task_dispatch)
class TestRunMultiExportHtmxBranch:
    def test_htmx_request_returns_204(self):
        url = reverse(
            'exports:run_multi_export', args=[multi_export_config().id]
        )
        response = authed_client().post(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 204

    def test_htmx_request_triggers_table_refresh(self):
        url = reverse(
            'exports:run_multi_export', args=[multi_export_config().id]
        )
        response = authed_client().post(url, HTTP_HX_REQUEST='true')
        assert response['HX-Trigger'] == 'runStarted'

    def test_htmx_request_creates_multi_export_run(self):
        config = multi_export_config()
        url = reverse('exports:run_multi_export', args=[config.id])
        authed_client().post(url, HTTP_HX_REQUEST='true')
        assert MultiProjectExportRun.objects.filter(
            config=config,
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

    @pytest.mark.parametrize('status,expected', [
        (ExportRun.Status.COMPLETED, 'completed'),
        (ExportRun.Status.FAILED, 'failed'),
        (ExportRun.Status.STARTED, 'started'),
    ])
    @use(authed_client, export_config)
    def test_renders_with_run_in_status(self, status, expected):
        config = export_config()
        ExportRun.objects.create(
            config=config,
            status=status,
        )
        response = authed_client().get(reverse('exports:home'))
        assert response.status_code == 200
        content = response.content.decode()
        assert config.name in content
        assert expected in content

    @use(authed_client, multi_export_config)
    def test_renders_multi_config_with_completed_run(self):
        config = multi_export_config()
        MultiProjectExportRun.objects.create(
            config=config,
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


@use(authed_client, multi_export_config)
class TestExportsRunButtonRendering:
    def test_multi_export_run_button_uses_multi_url(self):
        config = multi_export_config()
        url = reverse('exports:config_table')
        response = authed_client().get(url)
        content = response.content.decode()
        run_url = reverse('exports:run_multi_export', args=[config.id])
        assert f'hx-post="{run_url}"' in content
