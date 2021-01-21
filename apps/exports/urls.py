from django.urls import path
from . import views


app_name = 'exports'
urlpatterns = [
    path(r'', views.home, name='home'),
    path(r'create/', views.create_export_config, name='create_export_config'),
    path(r'create/multi-project/', views.create_multi_export_config, name='create_multi_export_config'),
    path(r'view/<int:export_id>/', views.export_details, name='export_details'),
    path(r'view/<int:export_id>/edit/', views.edit_export_config, name='edit_export_config'),
    path(r'view/<int:export_id>/delete/', views.delete_export_config, name='delete_export_config'),
    path(r'download/<int:export_id>/config-file/', views.download_export_file, name='download_export_file'),
    path(r'download/version/<int:version_id>/config-file/', views.download_export_file_version,
         name='download_export_file_version'),
    path(r'view/multi-project/<int:export_id>/', views.multi_export_details, name='multi_export_details'),
    path(r'view/multi-project/<int:export_id>/run/<int:run_id>/', views.multi_export_run_details,
         name='multi_export_run_details'),
    path(r'view/multi-project/<int:export_id>/edit/', views.edit_multi_export_config,
         name='edit_multi_export_config'),
    path(r'download/multi-project/<int:export_id>/config-file/', views.download_multi_export_file,
         name='download_multi_export_file'),
    path(r'api/run/<int:export_id>/', views.run_export, name='run_export'),
    path(r'api/run/multi-project/<int:export_id>/', views.run_multi_export, name='run_multi_export'),
    path(r'databases/', views.databases, name='databases'),
    path(r'databases/create/', views.create_database, name='create_database'),
    path(r'databases/<int:database_id>/edit/', views.edit_database, name='edit_database'),
]
