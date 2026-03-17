from unittest.mock import patch

import psycopg
import pytest

from ..models import RefreshRun
from ..runner import run_refresh


@pytest.mark.django_db
class TestRunRefresh:
    @patch('apps.refreshes.runner.refresh_materialized_view')
    def test_successful_refresh(self, mock_refresh_view, refresh_run):
        result = run_refresh(refresh_run)

        assert result.status == RefreshRun.Status.COMPLETED
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at > result.started_at
        assert 'All views refreshed successfully' in result.log
        assert len(result.view_results) == 2
        assert result.view_results['public.view1']['status'] == 'success'
        assert result.view_results['public.view2']['status'] == 'success'

    @patch('apps.refreshes.runner.refresh_materialized_view')
    def test_partial_failure(self, mock_refresh_view, refresh_run):
        mock_refresh_view.side_effect = [
            None,
            psycopg.Error('View does not exist'),
        ]

        result = run_refresh(refresh_run)

        assert result.status == RefreshRun.Status.FAILED
        assert len(result.view_results) == 2
        assert result.view_results['public.view1']['status'] == 'success'
        assert result.view_results['public.view2']['status'] == 'failed'
        assert (
            'View does not exist'
            in result.view_results['public.view2']['message']
        )
        assert 'Failed views: public.view2' in result.log

    @patch('apps.refreshes.runner.refresh_materialized_view')
    def test_all_views_fail(self, mock_refresh_view, refresh_run):
        mock_refresh_view.side_effect = psycopg.Error('Database error')

        result = run_refresh(refresh_run)

        assert result.status == RefreshRun.Status.FAILED
        assert len(result.view_results) == 2
        assert all(
            r['status'] == 'failed' for r in result.view_results.values()
        )

    @patch('apps.refreshes.runner.refresh_materialized_view')
    def test_view_results_include_duration(
        self, mock_refresh_view, refresh_run
    ):
        result = run_refresh(refresh_run)

        for view_result in result.view_results.values():
            assert 'duration' in view_result
            assert isinstance(view_result['duration'], float)
            assert view_result['duration'] >= 0

    @patch('apps.refreshes.runner.refresh_materialized_view')
    def test_view_without_schema_uses_public(
        self, mock_refresh_view, refresh_run
    ):
        refresh_run.refresh_config.materialized_views = ['view_no_schema']
        refresh_run.refresh_config.save()

        run_refresh(refresh_run)

        mock_refresh_view.assert_called_once()
        args = mock_refresh_view.call_args[0]
        assert args[1] == 'public'
        assert args[2] == 'view_no_schema'

    @patch('apps.refreshes.runner.refresh_materialized_view')
    def test_status_transitions(self, mock_refresh_view, refresh_run):
        assert refresh_run.status == RefreshRun.Status.QUEUED

        run_refresh(refresh_run)

        refresh_run.refresh_from_db()
        assert refresh_run.status == RefreshRun.Status.COMPLETED

    @patch('apps.refreshes.runner.refresh_materialized_view')
    def test_log_contains_timestamps(self, mock_refresh_view, refresh_run):
        result = run_refresh(refresh_run)

        assert 'Starting refresh' in result.log
        assert 'public.view1' in result.log
        assert 'public.view2' in result.log

    @patch('apps.refreshes.runner.refresh_materialized_view')
    def test_continues_on_view_failure(
        self, mock_refresh_view, refresh_run
    ):
        mock_refresh_view.side_effect = [
            psycopg.Error('First view failed'),
            None,
        ]

        result = run_refresh(refresh_run)

        assert mock_refresh_view.call_count == 2
        assert result.view_results['public.view1']['status'] == 'failed'
        assert result.view_results['public.view2']['status'] == 'success'
