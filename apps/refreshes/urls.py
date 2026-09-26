from django.urls import path

from . import views

app_name = 'refreshes'

urlpatterns = [
    path(
        '',
        views.refresh_configs,
        name='refresh_configs',
    ),
    path(
        'create/',
        views.create_refresh_config,
        name='create_refresh_config',
    ),
    path(
        '<int:config_id>/edit/',
        views.edit_refresh_config,
        name='edit_refresh_config',
    ),
    path(
        '<int:config_id>/delete/',
        views.delete_refresh_config,
        name='delete_refresh_config',
    ),
    path(
        '<int:config_id>/',
        views.refresh_details,
        name='refresh_details',
    ),
    path(
        '<int:config_id>/run-history-table/',
        views.run_history_table,
        name='run_history_table',
    ),
    path(
        '<int:config_id>/run/',
        views.run_refresh,
        name='run_refresh',
    ),
    path(
        'api/fetch-views/',
        views.fetch_materialized_views,
        name='fetch_materialized_views',
    ),
    path(r'config-table/', views.config_table, name='config_table'),
    path(r'runs/<int:run_id>/log/', views.run_log, name='run_log'),
    path(r'runs/<int:run_id>/status/', views.run_status, name='run_status'),
]
