from django.urls import path

from . import views


app_name = 'db'
urlpatterns = [
    path(r'', views.databases, name='databases'),
    path(r'create/', views.create_database, name='create_database'),
    path(
        r'<int:database_id>/edit/',
        views.edit_database,
        name='edit_database',
    ),
    path(
        r'<int:database_id>/delete/',
        views.delete_database,
        name='delete_database',
    ),
]
