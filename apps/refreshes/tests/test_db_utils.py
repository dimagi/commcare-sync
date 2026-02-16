from unittest.mock import MagicMock, patch

import psycopg

from ..db_utils import (
    check_connection,
    get_materialized_views,
    refresh_materialized_view,
)


@patch('apps.refreshes.db_utils.psycopg.connect')
def test_get_materialized_views_success(mock_connect):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ('public', 'view1', True),
        ('public', 'view2', False),
        ('custom', 'view3', True),
    ]
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(
        return_value=mock_cursor
    )
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_connect.return_value = mock_conn

    views = get_materialized_views('postgresql://localhost/test')

    assert len(views) == 3
    assert views[0]['full_name'] == 'public.view1'
    assert views[0]['schema'] == 'public'
    assert views[0]['name'] == 'view1'
    assert views[0]['has_unique_index'] is True
    assert views[1]['has_unique_index'] is False
    assert views[2]['schema'] == 'custom'


@patch('apps.refreshes.db_utils.psycopg.connect')
def test_refresh_materialized_view_success(mock_connect):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(
        return_value=mock_cursor
    )
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_connect.return_value = mock_conn

    refresh_materialized_view(
        'postgresql://localhost/test', 'public', 'view1'
    )

    mock_cursor.execute.assert_called_once()
    mock_connect.assert_called_once_with(
        'postgresql://localhost/test', autocommit=True
    )


@patch('apps.refreshes.db_utils.psycopg.connect')
def test_refresh_materialized_view_concurrently(mock_connect):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(
        return_value=mock_cursor
    )
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_connect.return_value = mock_conn

    refresh_materialized_view(
        'postgresql://localhost/test', 'public', 'view1', concurrently=True
    )

    executed_sql = mock_cursor.execute.call_args[0][0]
    # sql.Composed contains sql.SQL('CONCURRENTLY ') when concurrently=True
    assert any(
        'CONCURRENTLY' in getattr(part, '_obj', '')
        for part in executed_sql._obj
    )


@patch('apps.refreshes.db_utils.psycopg.connect')
def test_check_connection_success(mock_connect):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ['PostgreSQL 14.0']
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(
        return_value=mock_cursor
    )
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_connect.return_value = mock_conn

    success, message = check_connection('postgresql://localhost/test')

    assert success is True
    assert 'PostgreSQL' in message


@patch('apps.refreshes.db_utils.psycopg.connect')
def test_check_connection_failure(mock_connect):
    mock_connect.side_effect = psycopg.OperationalError('Connection failed')

    success, message = check_connection('postgresql://localhost/test')

    assert success is False
    assert 'Connection failed' in message
