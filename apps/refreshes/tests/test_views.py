import json
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from apps.db.models import Database

from ..models import RefreshConfig, RefreshRun

SCHEDULE_DEFAULTS = {
    'first_run_time': '00:00',
    'timezone': 'UTC',
}


@pytest.fixture
def client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def non_pg_database(db):
    return Database.objects.create(
        name='MySQL DB',
        connection_string='mysql://localhost/test',
    )


class TestRefreshConfigsListView:
    def test_requires_login(self, client, user):
        client.logout()
        url = reverse('refreshes:refresh_configs')
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_stats_in_context(self, client, db):
        url = reverse('refreshes:refresh_configs')
        response = client.get(url)
        assert 'export_stats' in response.context
        assert 'refresh_stats' in response.context
        assert 'forwarding_stats' in response.context

    def test_list_configs(self, client, refresh_config):
        url = reverse('refreshes:refresh_configs')
        response = client.get(url)
        assert response.status_code == 200
        assert refresh_config.name in response.content.decode()


class TestCreateRefreshConfigView:
    def test_get_form(self, client):
        url = reverse('refreshes:create_refresh_config')
        response = client.get(url)
        assert response.status_code == 200

    def test_create_valid(self, client, database):
        url = reverse('refreshes:create_refresh_config')
        response = client.post(
            url,
            {
                'name': 'New Config',
                'database': database.id,
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

    def test_create_missing_views(self, client, database):
        url = reverse('refreshes:create_refresh_config')
        response = client.post(
            url,
            {
                'name': 'Bad Config',
                'database': database.id,
                'materialized_views': '',
                **SCHEDULE_DEFAULTS,
            },
        )
        assert response.status_code == 200
        assert not RefreshConfig.objects.filter(name='Bad Config').exists()


class TestEditRefreshConfigView:
    def test_get_form(self, client, refresh_config):
        url = reverse(
            'refreshes:edit_refresh_config', args=[refresh_config.id]
        )
        response = client.get(url)
        assert response.status_code == 200

    def test_edit_valid(self, client, refresh_config):
        url = reverse(
            'refreshes:edit_refresh_config', args=[refresh_config.id]
        )
        response = client.post(
            url,
            {
                'name': 'Updated Name',
                'database': refresh_config.database.id,
                'materialized_views': json.dumps(['public.view1']),
                'concurrently': 'on',
                **SCHEDULE_DEFAULTS,
            },
        )
        assert response.status_code == 302
        refresh_config.refresh_from_db()
        assert refresh_config.name == 'Updated Name'
        assert refresh_config.materialized_views == ['public.view1']
        assert refresh_config.concurrently is True

    def test_edit_nonexistent_returns_404(self, client):
        url = reverse('refreshes:edit_refresh_config', args=[9999])
        response = client.get(url)
        assert response.status_code == 404


class TestDeleteRefreshConfigView:
    def test_get_confirmation(self, client, refresh_config):
        url = reverse(
            'refreshes:delete_refresh_config', args=[refresh_config.id]
        )
        response = client.get(url)
        assert response.status_code == 200

    def test_post_deletes(self, client, refresh_config):
        config_id = refresh_config.id
        url = reverse('refreshes:delete_refresh_config', args=[config_id])
        response = client.post(url)
        assert response.status_code == 302
        assert not RefreshConfig.objects.filter(id=config_id).exists()


class TestRefreshDetailsView:
    def test_details_page(self, client, refresh_config):
        url = reverse('refreshes:refresh_details', args=[refresh_config.id])
        response = client.get(url)
        assert response.status_code == 200
        assert refresh_config.name in response.content.decode()

    def test_hide_skipped(self, client, refresh_config):
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.SKIPPED,
        )
        url = reverse('refreshes:refresh_details', args=[refresh_config.id])
        response = client.get(url, {'hide_skipped': 'y'})
        assert response.status_code == 200


class TestRunHistoryTableView:
    def test_returns_partial(self, client, refresh_config):
        url = reverse('refreshes:run_history_table', args=[refresh_config.id])
        response = client.get(url)
        assert response.status_code == 200

    def test_post_not_allowed(self, client, refresh_config):
        url = reverse('refreshes:run_history_table', args=[refresh_config.id])
        response = client.post(url)
        assert response.status_code == 405


class TestRunRefreshView:
    @patch('apps.refreshes.views.run_refresh_task')
    def test_triggers_task(self, mock_task, client, refresh_config):
        mock_result = MagicMock()
        mock_result.task_id = 'test-task-id'
        mock_task.delay.return_value = mock_result

        url = reverse('refreshes:run_refresh', args=[refresh_config.id])
        response = client.post(url)

        assert response.status_code == 200
        assert response.content.decode() == 'test-task-id'
        mock_task.delay.assert_called_once()
        assert RefreshRun.objects.filter(
            refresh_config=refresh_config,
            triggered_from_ui=True,
        ).exists()

    def test_get_not_allowed(self, client, refresh_config):
        url = reverse('refreshes:run_refresh', args=[refresh_config.id])
        response = client.get(url)
        assert response.status_code == 405


class TestFetchMaterializedViewsView:
    def test_missing_database_id(self, client):
        url = reverse('refreshes:fetch_materialized_views')
        response = client.get(url)
        assert response.status_code == 400

    def test_nonexistent_database(self, client):
        url = reverse('refreshes:fetch_materialized_views')
        response = client.get(url, {'database_id': 9999})
        assert response.status_code == 404

    def test_non_postgresql_database(self, client, non_pg_database):
        url = reverse('refreshes:fetch_materialized_views')
        response = client.get(url, {'database_id': non_pg_database.id})
        assert response.status_code == 400
        data = response.json()
        assert 'PostgreSQL' in data['error']

    @patch('apps.refreshes.views.check_connection')
    @patch('apps.refreshes.views.get_materialized_views')
    def test_success(self, mock_get_views, mock_check_conn, client, database):
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
        response = client.get(url, {'database_id': database.id})

        assert response.status_code == 200
        data = response.json()
        assert len(data['views']) == 1
        assert data['views'][0]['full_name'] == 'public.view1'

    @patch('apps.refreshes.views.check_connection')
    def test_connection_failure(self, mock_check_conn, client, database):
        mock_check_conn.return_value = (False, 'Connection refused')

        url = reverse('refreshes:fetch_materialized_views')
        response = client.get(url, {'database_id': database.id})

        assert response.status_code == 500
        assert 'error' in response.json()

    def test_post_not_allowed(self, client):
        url = reverse('refreshes:fetch_materialized_views')
        response = client.post(url)
        assert response.status_code == 405


import re


class TestRefreshConfigTableView:
    def test_requires_login(self, client, user):
        client.logout()
        response = client.get(reverse('refreshes:config_table'))
        assert response.status_code == 302

    def test_returns_200(self, client, db):
        response = client.get(reverse('refreshes:config_table'))
        assert response.status_code == 200

    def test_config_appears(self, client, refresh_config):
        response = client.get(reverse('refreshes:config_table'))
        assert refresh_config.name in response.content.decode()

    def test_pagination_default_10(self, client, database):
        for i in range(15):
            from ..models import RefreshConfig
            RefreshConfig.objects.create(
                name=f'Refresh {i}',
                database=database,
                materialized_views=['public.view1'],
            )
        response = client.get(reverse('refreshes:config_table'))
        shown = response.content.decode().count('Refresh ')
        assert shown == 10

    def test_etag_match_returns_no_swap(self, client, refresh_config):
        response = client.get(reverse('refreshes:config_table'))
        match = re.search(r'data-etag="([a-f0-9]+)"', response.content.decode())
        assert match
        etag = match.group(1)
        response2 = client.get(reverse('refreshes:config_table'), {'etag': etag})
        assert response2.get('HX-Reswap') == 'none'

    def test_etag_mismatch_returns_content(self, client, refresh_config):
        response = client.get(reverse('refreshes:config_table'), {'etag': 'stale'})
        assert response.get('HX-Reswap') is None
        assert refresh_config.name in response.content.decode()


class TestRefreshRunLogView:
    def test_requires_login(self, client, user, refresh_config):
        run = RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.COMPLETED,
            log='hello log',
        )
        client.logout()
        response = client.get(reverse('refreshes:run_log', args=[run.id]))
        assert response.status_code == 302

    def test_returns_log(self, client, refresh_config):
        run = RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.COMPLETED,
            log='refresh log content',
        )
        response = client.get(reverse('refreshes:run_log', args=[run.id]))
        assert response.status_code == 200
        assert 'refresh log content' in response.content.decode()

    def test_404_for_missing(self, client):
        response = client.get(reverse('refreshes:run_log', args=[9999]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestRefreshesListPageSmoke:
    """Smoke tests: full-page renders with configs in various run states."""

    def test_renders_200(self, client, db):
        response = client.get(reverse('refreshes:refresh_configs'))
        assert response.status_code == 200

    def test_includes_config_table_div(self, client, db):
        response = client.get(reverse('refreshes:refresh_configs'))
        assert 'id="refreshes-config-table"' in response.content.decode()

    def test_renders_with_no_runs(self, client, refresh_config):
        """Template handles configs with no runs (Never / — paths)."""
        response = client.get(reverse('refreshes:refresh_configs'))
        assert response.status_code == 200
        assert refresh_config.name in response.content.decode()

    def test_renders_with_completed_run(self, client, refresh_config):
        """Completed run: status icon, log button enabled, duration displayed."""
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.COMPLETED,
            log='Refreshed 2 views.',
        )
        response = client.get(reverse('refreshes:refresh_configs'))
        assert response.status_code == 200
        assert 'completed' in response.content.decode()

    def test_renders_with_failed_run(self, client, refresh_config):
        """Failed run: log button enabled."""
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.FAILED,
            log='Error refreshing.',
        )
        response = client.get(reverse('refreshes:refresh_configs'))
        assert response.status_code == 200
        assert 'failed' in response.content.decode()

    def test_renders_with_started_run(self, client, refresh_config):
        """In-progress run: log button disabled."""
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.STARTED,
        )
        response = client.get(reverse('refreshes:refresh_configs'))
        assert response.status_code == 200
        assert 'started' in response.content.decode()
