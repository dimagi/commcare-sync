"""PostgreSQL database utilities for materialized view operations."""
import logging

import psycopg
from psycopg import sql

logger = logging.getLogger(__name__)


def get_materialized_views(connection_string):
    """
    Query PostgreSQL database for list of materialized views.

    Returns list of dicts with keys: schema, name, full_name.
    """
    query = """
        SELECT
            m.schemaname,
            m.matviewname,
            EXISTS (
                SELECT 1
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = m.matviewname
                AND n.nspname = m.schemaname
                AND i.indisunique = true
            ) AS has_unique_index
        FROM pg_matviews m
        WHERE m.schemaname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY m.schemaname, m.matviewname;
    """
    try:
        with psycopg.connect(connection_string) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                return [
                    {
                        'schema': row[0],
                        'name': row[1],
                        'full_name': f'{row[0]}.{row[1]}',
                        'has_unique_index': row[2],
                    }
                    for row in cursor.fetchall()
                ]
    except psycopg.Error as e:
        logger.error(f'Error fetching materialized views: {e}')
        raise


def refresh_materialized_view(
    connection_string, schema_name, view_name, concurrently=False
):
    """
    Execute REFRESH MATERIALIZED VIEW command.

    Uses autocommit since REFRESH is DDL.
    If concurrently is True, uses CONCURRENTLY to avoid exclusive locks
    (requires a unique index on the view).
    """
    try:
        with psycopg.connect(connection_string, autocommit=True) as conn:
            with conn.cursor() as cursor:
                template = 'REFRESH MATERIALIZED VIEW {concurrently}{schema}.{view}'
                refresh_cmd = sql.SQL(template).format(
                    concurrently=sql.SQL(
                        'CONCURRENTLY ' if concurrently else ''
                    ),
                    schema=sql.Identifier(schema_name),
                    view=sql.Identifier(view_name),
                )
                cursor.execute(refresh_cmd)
                logger.info(
                    f'Successfully refreshed {schema_name}.{view_name}'
                )
    except psycopg.Error as e:
        logger.error(f'Error refreshing {schema_name}.{view_name}: {e}')
        raise


def check_connection(connection_string):
    """
    Test database connection.

    Returns (success: bool, message: str).
    """
    try:
        with psycopg.connect(connection_string) as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT version();')
                version = cursor.fetchone()[0]
                return True, f'Connection successful. {version}'
    except psycopg.Error as e:
        return False, f'Connection failed: {str(e)}'
