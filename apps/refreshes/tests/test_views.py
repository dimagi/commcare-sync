import json
import re
from unittest.mock import MagicMock, patch

from django.urls import reverse
from unmagic import fixture, use

from apps.db.models import Database
from tests.fixtures import authed_client, database

from ..models import RefreshConfig, RefreshRun
from .fixtures import refresh_config as _refresh_config

SCHEDULE_DEFAULTS = {
    'first_run_time': '00:00',
    'timezone': 'UTC',
}


@fixture
@use('db')
def non_pg_database():
    yield Database.objects.create(
        name='MySQL DB',
        connection_string='mysql://localhost/test',
    )


class TestRefreshConfigsListView:
    @use(authed_client)
    def test_requires_login(self):
        client = authed_client()
        client.logout()
        url = reverse('refreshes:refresh_configs')
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    @use(authed_client, 'db')
    def test_stats_in_context(self):
        url = reverse('refreshes:refresh_configs')
        response = authed_client().get(url)
        assert 'export_stats' in response.context
        assert 'refresh_stats' in response.context
        assert 'forwarding_stats' in response.context

    @use(authed_client, _refresh_config)
    def test_list_configs(self):
        config = _refresh_config()
        url = reverse('refreshes:refresh_configs')
        response = authed_client().get(url)
        assert response.status_code == 200
        assert config.name in response.content.decode()


class TestCreateRefreshConfigView:
    @use(authed_client)
    def test_get_form(self):
        url = reverse('refreshes:create_refresh_config')
        response = authed_client().get(url)
        assert response.status_code == 200

    @use(authed_client, database)
    def test_create_valid(self):
        db_obj = database()
        url = reverse('refreshes:create_refresh_config')
        response = authed_client().post(
            url,
            {
                'name': 'New Config',
                'database': db_obj.id,
                'materialized_views': json.dumps(['public.my_view']),
                'concurrently': '',
                **SCHEDULE_DEFAULTS,
            },
        )
        assert response.status_code == 302
        config = RefreshConfig.objects.get(name='New Config')
        assert config.materialized_views == ['public.my_view']
        assert config.concurrently is False
        assert response.url == reverse(
            'refreshes:refresh_details', args=[config.id]
        )

    @use(authed_client, database)
    def test_create_missing_views(self):
        db_obj = database()
        url = reverse('refreshes:create_refresh_config')
        response = authed_client().post(
            url,
            {
                'name': 'Bad Config',
                'database': db_obj.id,
                'materialized_views': '',
                **SCHEDULE_DEFAULTS,
            },
        )
        assert response.status_code == 200
        assert not RefreshConfig.objects.filter(name='Bad Config').exists()


class TestEditRefreshConfigView:
    @use(authed_client, _refresh_config)
    def test_get_form(self):
        config = _refresh_config()
        url = reverse('refreshes:edit_refresh_config', args=[config.id])
        response = authed_client().get(url)
        assert response.status_code == 200

    @use(authed_client, _refresh_config)
    def test_edit_valid(self):
        config = _refresh_config()
        url = reverse('refreshes:edit_refresh_config', args=[config.id])
        response = authed_client().post(
            url,
            {
                'name': 'Updated Name',
                'database': config.database.id,
                'materialized_views': json.dumps(['public.view1']),
                'concurrently': 'on',
                **SCHEDULE_DEFAULTS,
            },
        )
        assert response.status_code == 302
        config.refresh_from_db()
        assert config.name == 'Updated Name'
        assert config.materialized_views == ['public.view1']
        assert config.concurrently is True

    @use(authed_client)
    def test_edit_nonexistent_returns_404(self):
        url = reverse('refreshes:edit_refresh_config', args=[9999])
        response = authed_client().get(url)
        assert response.status_code == 404


class TestDeleteRefreshConfigView:
    @use(authed_client, _refresh_config)
    def test_get_confirmation(self):
        config = _refresh_config()
        url = reverse('refreshes:delete_refresh_config', args=[config.id])
        response = authed_client().get(url)
        assert response.status_code == 200

    @use(authed_client, _refresh_config)
    def test_post_deletes(self):
        config_id = _refresh_config().id
        url = reverse('refreshes:delete_refresh_config', args=[config_id])
        response = authed_client().post(url)
        assert response.status_code == 302
        assert not RefreshConfig.objects.filter(id=config_id).exists()


class TestRefreshDetailsView:
    @use(authed_client, _refresh_config)
    def test_details_page(self):
        config = _refresh_config()
        url = reverse('refreshes:refresh_details', args=[config.id])
        response = authed_client().get(url)
        assert response.status_code == 200
        assert config.name in response.content.decode()

    @use(authed_client, _refresh_config)
    def test_hide_skipped(self):
        config = _refresh_config()
        RefreshRun.objects.create(
            refresh_config=config,
            status=RefreshRun.Status.SKIPPED,
        )
        url = reverse('refreshes:refresh_details', args=[config.id])
        response = authed_client().get(url, {'hide_skipped': 'y'})
        assert response.status_code == 200


class TestRunHistoryTableView:
    @use(authed_client, _refresh_config)
    def test_returns_partial(self):
        config = _refresh_config()
        url = reverse('refreshes:run_history_table', args=[config.id])
        response = authed_client().get(url)
        assert response.status_code == 200

    @use(authed_client, _refresh_config)
    def test_post_not_allowed(self):
        config = _refresh_config()
        url = reverse('refreshes:run_history_table', args=[config.id])
        response = authed_client().post(url)
        assert response.status_code == 405


class TestRunRefreshView:
    @use(authed_client, _refresh_config)
    @patch('apps.refreshes.views.run_refresh_task')
    def test_triggers_task(self, mock_task):
        config = _refresh_config()
        mock_result = MagicMock()
        mock_result.task_id = 'test-task-id'
        mock_task.delay.return_value = mock_result

        url = reverse('refreshes:run_refresh', args=[config.id])
        response = authed_client().post(url)

        assert response.status_code == 200
        assert response.content.decode() == 'test-task-id'
        mock_task.delay.assert_called_once()
        assert RefreshRun.objects.filter(
            refresh_config=config,
            triggered_from_ui=True,
        ).exists()

    @use(authed_client, _refresh_config)
    def test_get_not_allowed(self):
        config = _refresh_config()
        url = reverse('refreshes:run_refresh', args=[config.id])
        response = authed_client().get(url)
        assert response.status_code == 405


class TestFetchMaterializedViewsView:
    @use(authed_client)
    def test_missing_database_id(self):
        url = reverse('refreshes:fetch_materialized_views')
        response = authed_client().get(url)
        assert response.status_code == 400

    @use(authed_client)
    def test_nonexistent_database(self):
        url = reverse('refreshes:fetch_materialized_views')
        response = authed_client().get(url, {'database_id': 9999})
        assert response.status_code == 404

    @use(authed_client, non_pg_database)
    def test_non_postgresql_database(self):
        db_obj = non_pg_database()
        url = reverse('refreshes:fetch_materialized_views')
        response = authed_client().get(url, {'database_id': db_obj.id})
        assert response.status_code == 400
        data = response.json()
        assert 'PostgreSQL' in data['error']

    @use(authed_client, database)
    @patch('apps.refreshes.views.check_connection')
    @patch('apps.refreshes.views.get_materialized_views')
    def test_success(self, mock_get_views, mock_check_conn):
        db_obj = database()
        mock_check_conn.return_value = (True, 'OK')
        mock_get_views.return_value = [
            {
                'schema': 'public',
                'name': 'view1',
                'full_name': 'public.view1',
                'has_unique_index': True,
            },
        ]

        url = reverse('refreshes:fetch_materialized_views')
        response = authed_client().get(url, {'database_id': db_obj.id})

        assert response.status_code == 200
        data = response.json()
        assert len(data['views']) == 1
        assert data['views'][0]['full_name'] == 'public.view1'

    @use(authed_client, database)
    @patch('apps.refreshes.views.check_connection')
    def test_connection_failure(self, mock_check_conn):
        db_obj = database()
        mock_check_conn.return_value = (False, 'Connection refused')

        url = reverse('refreshes:fetch_materialized_views')
        response = authed_client().get(url, {'database_id': db_obj.id})

        assert response.status_code == 500
        assert 'error' in response.json()

    @use(authed_client)
    def test_post_not_allowed(self):
        url = reverse('refreshes:fetch_materialized_views')
        response = authed_client().post(url)
        assert response.status_code == 405



class TestRefreshConfigTableView:
    @use(authed_client)
    def test_requires_login(self):
        client = authed_client()
        client.logout()
        response = client.get(reverse('refreshes:config_table'))
        assert response.status_code == 302

    @use(authed_client, 'db')
    def test_returns_200(self):
        response = authed_client().get(reverse('refreshes:config_table'))
        assert response.status_code == 200

    @use(authed_client, _refresh_config)
    def test_config_appears(self):
        config = _refresh_config()
        response = authed_client().get(reverse('refreshes:config_table'))
        assert config.name in response.content.decode()

    @use(authed_client, database)
    def test_pagination_default_10(self):
        db_obj = database()
        for i in range(15):
            RefreshConfig.objects.create(
                name=f'Refresh {i}',
                database=db_obj,
                materialized_views=['public.view1'],
            )
        response = authed_client().get(reverse('refreshes:config_table'))
        shown = response.content.decode().count('Refresh ')
        assert shown == 10

    @use(authed_client, _refresh_config)
    def test_etag_match_returns_no_swap(self):
        _refresh_config()
        client = authed_client()
        response = client.get(reverse('refreshes:config_table'))
        match = re.search(r'"etag":\s*"([a-f0-9]+)"', response.content.decode())
        assert match
        etag = match.group(1)
        response2 = client.get(reverse('refreshes:config_table'), {'etag': etag})
        assert response2.get('HX-Reswap') == 'none'

    @use(authed_client, _refresh_config)
    def test_etag_mismatch_returns_content(self):
        config = _refresh_config()
        response = authed_client().get(
            reverse('refreshes:config_table'), {'etag': 'stale'}
        )
        assert response.get('HX-Reswap') is None
        assert config.name in response.content.decode()


class TestRefreshRunLogView:
    @use(authed_client, _refresh_config)
    def test_requires_login(self):
        run = RefreshRun.objects.create(
            refresh_config=_refresh_config(),
            status=RefreshRun.Status.COMPLETED,
            log='hello log',
        )
        client = authed_client()
        client.logout()
        response = client.get(reverse('refreshes:run_log', args=[run.id]))
        assert response.status_code == 302

    @use(authed_client, _refresh_config)
    def test_returns_log(self):
        run = RefreshRun.objects.create(
            refresh_config=_refresh_config(),
            status=RefreshRun.Status.COMPLETED,
            log='refresh log content',
        )
        response = authed_client().get(reverse('refreshes:run_log', args=[run.id]))
        assert response.status_code == 200
        assert 'refresh log content' in response.content.decode()

    @use(authed_client)
    def test_404_for_missing(self):
        response = authed_client().get(reverse('refreshes:run_log', args=[9999]))
        assert response.status_code == 404


class TestRefreshesListPageSmoke:
    """Smoke tests: full-page renders with configs in various run states."""

    @use(authed_client, 'db')
    def test_renders_200(self):
        response = authed_client().get(reverse('refreshes:refresh_configs'))
        assert response.status_code == 200

    @use(authed_client, 'db')
    def test_includes_config_table_div(self):
        response = authed_client().get(reverse('refreshes:refresh_configs'))
        assert 'id="refreshes-config-table"' in response.content.decode()

    @use(authed_client, _refresh_config)
    def test_renders_with_no_runs(self):
        config = _refresh_config()
        response = authed_client().get(reverse('refreshes:refresh_configs'))
        assert response.status_code == 200
        assert config.name in response.content.decode()

    @use(authed_client, _refresh_config)
    def test_renders_with_completed_run(self):
        RefreshRun.objects.create(
            refresh_config=_refresh_config(),
            status=RefreshRun.Status.COMPLETED,
            log='Refreshed 2 views.',
        )
        response = authed_client().get(reverse('refreshes:refresh_configs'))
        assert response.status_code == 200
        assert 'completed' in response.content.decode()

    @use(authed_client, _refresh_config)
    def test_renders_with_failed_run(self):
        RefreshRun.objects.create(
            refresh_config=_refresh_config(),
            status=RefreshRun.Status.FAILED,
            log='Error refreshing.',
        )
        response = authed_client().get(reverse('refreshes:refresh_configs'))
        assert response.status_code == 200
        assert 'failed' in response.content.decode()

    @use(authed_client, _refresh_config)
    def test_renders_with_started_run(self):
        RefreshRun.objects.create(
            refresh_config=_refresh_config(),
            status=RefreshRun.Status.STARTED,
        )
        response = authed_client().get(reverse('refreshes:refresh_configs'))
        assert response.status_code == 200
        assert 'started' in response.content.decode()
